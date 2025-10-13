/**
 * SOGo SQL Groups Expansion Patch
 *
 * Extends SOGo's Card and Attendees services to support SQL-based groups from edulution_gal.
 * This patch enables group expansion for SQL groups without requiring LDAP.
 *
 * Features:
 * - Makes SQL groups expandable (isGroup=1 from edulution_gal)
 * - Redirects /members requests to custom PHP middleware
 * - Works with email composer, contacts module, AND calendar invitations
 * - Patches both Card service (for mail/contacts) and Attendees service (for calendar)
 */

console.log('[SQL Groups] Script file loaded!');

(function() {
  'use strict';

  console.log('[SQL Groups] IIFE started');

  // Wait for Angular to be fully loaded
  function initSQLGroupsPatch() {
    // Check if Angular is available
    if (typeof angular === 'undefined') {
      console.log('[SQL Groups] Waiting for Angular to load...');
      setTimeout(initSQLGroupsPatch, 100);
      return;
    }

    // Try to patch Card service (for Contacts and Email)
    try {
      angular.module('SOGo.ContactsUI').run(['Card', '$http', function(Card, $http) {

        console.log('[SQL Groups] Patching Card service for SQL group support');

    // Store original functions
    var originalIsGroup = Card.prototype.$isGroup;
    var originalMembers = Card.prototype.$members;

    /**
     * Patched $isGroup to support SQL groups
     * SQL groups have isGroup=1 from edulution_gal view
     */
    Card.prototype.$isGroup = function(options) {
      // Check if this is a SQL group (isGroup field exists and is truthy)
      var isSQLGroup = this.isgroup || (this.isGroup && this.isGroup === 1);

      if (isSQLGroup) {
        // SQL groups are always expandable (we have groupMembers in the view)
        return true;
      }

      // Fall back to original LDAP group check
      return originalIsGroup.call(this, options);
    };

    /**
     * Patched $members to use PHP middleware for SQL groups
     */
    Card.prototype.$members = function() {
      var _this = this;

      // If members already loaded, return them
      if (this.members) {
        return Card.$q.when(this.members);
      }

      // Check if this is a SQL group
      var isSQLGroup = this.isgroup || (this.isGroup && this.isGroup === 1);

      if (isSQLGroup) {
        // Use our custom PHP middleware for SQL groups
        var email = this.c_uid || this.id;
        var url = '/SOGo/so/' + Card.$resource.activeUser.login +
                  '/Contacts/' + this.pid + '/' + email + '/members';

        console.log('[SQL Groups] Fetching members for SQL group:', email);

        return $http.get(url).then(function(response) {
          var data = response.data;

          if (data.members && Array.isArray(data.members)) {
            _this.members = _.map(data.members, function(member) {
              return new Card(member);
            });
            console.log('[SQL Groups] Loaded', _this.members.length, 'members for', email);
            return _this.members;
          } else {
            console.error('[SQL Groups] Invalid response format:', data);
            return Card.$q.reject("Invalid members response");
          }
        }).catch(function(error) {
          console.error('[SQL Groups] Failed to fetch members:', error);

          // If our endpoint fails, try the PHP middleware directly
          return $http.get('/group-resolver.php?email=' + encodeURIComponent(email) + '&action=members')
            .then(function(response) {
              var data = response.data;
              if (data.members && Array.isArray(data.members)) {
                _this.members = _.map(data.members, function(member) {
                  return new Card(member);
                });
                console.log('[SQL Groups] Loaded', _this.members.length, 'members via direct endpoint');
                return _this.members;
              }
              return Card.$q.reject("Invalid members response from middleware");
            })
            .catch(function(err) {
              console.error('[SQL Groups] Both endpoints failed:', err);
              return Card.$q.reject("Failed to fetch SQL group members");
            });
        });
      }

      // Check if this is an LDAP group
      if (this.$isGroup({expandable: true})) {
        console.log('[SQL Groups] Falling back to LDAP group expansion');
        return originalMembers.call(this);
      }

      return Card.$q.reject("Card " + this.id + " is not a group");
    };

        console.log('[SQL Groups] Card service patched successfully');
      }]);
    } catch(e) {
      console.log('[SQL Groups] ContactsUI module not available on this page:', e.message);
    }

      // Patch Attendees service (for Calendar invitations)
    // Wait for SchedulerUI module to load
    setTimeout(function() {
      try {
        angular.module('SOGo.SchedulerUI').run(['Attendees', function(Attendees) {

          console.log('[SQL Groups] Patching Attendees service for SQL group support in Calendar');

        // Store original add function
        var originalAdd = Attendees.prototype.add;

        /**
         * Patched add() to expand SQL groups in calendar invitations
         */
        Attendees.prototype.add = function(card, options) {
          var _this = this;
          var attendee, promise = Attendees.$q.when();

          if (card && !card.$isList({expandable: true})) {
            // Check if this is a SQL group (not an expandable LDAP list)
            var isSQLGroup = card.isgroup || (card.isGroup && card.isGroup === 1);

            if (isSQLGroup && card.$isGroup && card.$isGroup()) {
              // This is a SQL group - expand it
              console.log('[SQL Groups] Expanding SQL group in calendar:', card.$$email || card.c_uid);

              // Initialize organizer if needed
              if (!this.component.attendees || (options && options.organizerCalendar)) {
                this.initOrganizer(options? options.organizerCalendar : null);
              }

              // Fetch members and add them individually
              promise = card.$members().then(function(members) {
                console.log('[SQL Groups] Adding', members.length, 'members from SQL group');

                // Add each member as an individual attendee
                var addPromises = [];
                _.forEach(members, function(member) {
                  // Create attendee object
                  attendee = {
                    uid: member.c_uid,
                    domain: member.c_domain,
                    isGroup: false,
                    isExpandableGroup: false,
                    isResource: member.isresource,
                    name: member.c_cn,
                    email: member.$$email || (member.emails && member.emails[0] && member.emails[0].value),
                    role: Attendees.ROLES.REQ_PARTICIPANT,
                    partstat: 'needs-action',
                    $avatarIcon: 'person'
                  };

                  // Check if not already an attendee
                  if (!_.find(_this.component.attendees, function(o) {
                    return o.email == attendee.email;
                  })) {
                    attendee.image = Attendees.$gravatar(attendee.email, 32);
                    if (_this.component.attendees)
                      _this.component.attendees.push(attendee);
                    else
                      _this.component.attendees = [attendee];
                    _this.updateFreeBusyAttendee(attendee);
                  }
                });

                return Attendees.$q.all(addPromises);
              }).catch(function(error) {
                console.error('[SQL Groups] Failed to expand SQL group in calendar:', error);
                // Fall back to original behavior
                return originalAdd.call(_this, card, options);
              });

              return promise;
            }
          }

          // Not a SQL group, use original function
          return originalAdd.call(this, card, options);
        };

          console.log('[SQL Groups] Attendees service patched successfully');
        }]);
      } catch(e) {
        console.log('[SQL Groups] SchedulerUI module not available on this page:', e.message);
      }
    }, 1000); // Wait 1 second for SchedulerUI module to load
  }

  // Start initialization
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSQLGroupsPatch);
  } else {
    initSQLGroupsPatch();
  }

})();
