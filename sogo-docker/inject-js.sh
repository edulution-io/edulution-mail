#!/bin/bash
# Inject SQL groups JavaScript into SOGo's main UI template

# Work on the rsync'ed files in /sogo_web/ (the actual served files)
TEMPLATE_FILE="/sogo_web/Templates/UIxPageFrame.wox"
JS_SCRIPT='    <script type="text/javascript" src="js/sql-groups.js"></script>'

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
