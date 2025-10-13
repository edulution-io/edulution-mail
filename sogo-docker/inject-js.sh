#!/bin/bash
# Inject SQL groups JavaScript into SOGo's main UI template

# Patch the source template (before rsync to /sogo_web/)
TEMPLATE_FILE="/usr/lib/GNUstep/SOGo/Templates/UIxPageFrame.wox"
# Use absolute path to ensure it works from any page
JS_SCRIPT='    <script type="text/javascript" src="/SOGo/WebServerResources/js/sql-groups.js"></script>'

# Check if the injection has already been done
if grep -q "sql-groups.js" "$TEMPLATE_FILE" 2>/dev/null; then
    echo "SQL groups JavaScript already injected into SOGo template"
    exit 0
fi

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "WARNING: Template file $TEMPLATE_FILE not found - JavaScript will not be loaded automatically"
    exit 1
fi

# Inject the script tag before the closing </head> tag
if grep -q "</head>" "$TEMPLATE_FILE"; then
    sed -i "s|</head>|$JS_SCRIPT\n  </head>|" "$TEMPLATE_FILE"
    echo "Successfully injected SQL groups JavaScript into SOGo template"
else
    echo "WARNING: Could not find </head> tag in template file"
    exit 1
fi
