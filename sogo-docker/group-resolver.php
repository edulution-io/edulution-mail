<?php
/**
 * SOGo Group Resolver Middleware
 *
 * Provides group member resolution for SQL-based groups in SOGo.
 * This middleware resolves group members from the edulution_gal SQL view
 * and provides them in a format compatible with SOGo's frontend.
 *
 * Endpoints:
 * - GET /group-resolver.php?email=<group-email>&action=members
 * - GET /group-resolver.php?email=<group-email>&action=check
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Get database credentials from environment
$dbHost = getenv('DBHOST') ?: 'unix_socket=/var/run/mysqld/mysqld.sock';
$dbUser = getenv('DBUSER') ?: 'mailcow';
$dbPass = getenv('DBPASS') ?: '';
$dbName = getenv('DBNAME') ?: 'mailcow';

// Parse parameters
$email = $_GET['email'] ?? '';
$action = $_GET['action'] ?? 'members';

if (empty($email)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing email parameter']);
    exit;
}

// Connect to database
try {
    $pdo = new PDO(
        "mysql:unix_socket=/var/run/mysqld/mysqld.sock;dbname={$dbName}",
        $dbUser,
        $dbPass,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database connection failed']);
    error_log("Group resolver DB error: " . $e->getMessage());
    exit;
}

/**
 * Check if an email is a group
 */
function isGroup($pdo, $email) {
    $stmt = $pdo->prepare("
        SELECT isGroup, groupMembers
        FROM edulution_gal
        WHERE c_uid = :email AND isGroup = 1
    ");
    $stmt->execute(['email' => $email]);
    return $stmt->fetch(PDO::FETCH_ASSOC);
}

/**
 * Recursively resolve group members
 */
function resolveGroupMembers($pdo, $email, &$processed = []) {
    // Prevent infinite loops
    if (in_array($email, $processed)) {
        return [];
    }
    $processed[] = $email;

    $groupInfo = isGroup($pdo, $email);

    if (!$groupInfo) {
        // Not a group, return as regular member
        $stmt = $pdo->prepare("
            SELECT c_uid, c_cn, c_mail
            FROM edulution_gal
            WHERE c_uid = :email
        ");
        $stmt->execute(['email' => $email]);
        $member = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($member) {
            return [[
                'c_uid' => $member['c_uid'],
                'c_cn' => $member['c_cn'] ?: $member['c_uid'],
                'emails' => [[
                    'value' => $member['c_mail'] ?: $member['c_uid'],
                    'type' => 'work'
                ]]
            ]];
        }
        return [];
    }

    // Parse group members (space-separated)
    $groupMembers = $groupInfo['groupMembers'];
    $memberEmails = preg_split('/\s+/', trim($groupMembers));

    $allMembers = [];
    foreach ($memberEmails as $memberEmail) {
        $memberEmail = trim($memberEmail);
        if (empty($memberEmail)) {
            continue;
        }

        // Check if this member is also a group (recursive)
        $nestedMembers = resolveGroupMembers($pdo, $memberEmail, $processed);
        $allMembers = array_merge($allMembers, $nestedMembers);
    }

    return $allMembers;
}

// Handle actions
switch ($action) {
    case 'check':
        // Check if email is a group
        $groupInfo = isGroup($pdo, $email);
        if ($groupInfo) {
            echo json_encode([
                'isGroup' => true,
                'email' => $email,
                'memberCount' => count(preg_split('/\s+/', trim($groupInfo['groupMembers'])))
            ]);
        } else {
            echo json_encode(['isGroup' => false]);
        }
        break;

    case 'members':
        // Resolve and return all group members
        $groupInfo = isGroup($pdo, $email);
        if (!$groupInfo) {
            http_response_code(404);
            echo json_encode(['error' => 'Not a group or group not found']);
            exit;
        }

        $processed = [];
        $members = resolveGroupMembers($pdo, $email, $processed);

        echo json_encode([
            'group' => $email,
            'members' => $members,
            'count' => count($members)
        ]);
        break;

    default:
        http_response_code(400);
        echo json_encode(['error' => 'Invalid action']);
}
?>
