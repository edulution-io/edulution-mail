/**
 * SOGo SQL Groups Expansion Patch
 *
 * Extends SOGo's Card service to support SQL-based groups from edulution_gal.
 * This patch enables group expansion for SQL groups without requiring LDAP.
 *
 * Features:
 * - Makes SQL groups expandable (isGroup=1 from edulution_gal)
 * - Redirects /members requests to custom PHP middleware
 * - Works with both email composer and contacts module
 */

(function() {
  'use strict';

  // Wait for Angular and Card service to be available
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
})();
