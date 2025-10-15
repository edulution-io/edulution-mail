<?php
/**
 * SQL Group Members Resolver
 * Returns group members in SOGo's expected format
 */

header('Content-Type: application/json');

// Get group ID from URL
$requestUri = $_SERVER['REQUEST_URI'];
preg_match('/\/Contacts\/linuxmuster_groups\/([^\/]+)\/members/', $requestUri, $matches);
$groupId = $matches[1] ?? '';

if (empty($groupId)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing group ID']);
    exit;
}

// Database connection
$dbHost = getenv('DBHOST') ?: 'unix_socket=/var/run/mysqld/mysqld.sock';
$dbUser = getenv('DBUSER') ?: 'mailcow';
$dbPass = getenv('DBPASS') ?: '';
$dbName = getenv('DBNAME') ?: 'mailcow';

try {
    $pdo = new PDO("mysql:$dbHost;dbname=$dbName", $dbUser, $dbPass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database connection failed']);
    exit;
}

// Get group
$stmt = $pdo->prepare("
    SELECT c_uid, c_cn, groupMembers, isGroup
    FROM edulution_gal
    WHERE c_uid = :group_id AND isGroup = 1
");
$stmt->execute(['group_id' => $groupId]);
$group = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$group) {
    http_response_code(404);
    echo json_encode(['error' => 'Group not found', 'members' => []]);
    exit;
}

// Parse members (space-separated emails)
$memberEmails = array_filter(explode(' ', $group['groupMembers'] ?? ''));

if (empty($memberEmails)) {
    echo json_encode(['members' => []]);
    exit;
}

// Get member details
$placeholders = implode(',', array_fill(0, count($memberEmails), '?'));
$stmt = $pdo->prepare("
    SELECT
        c_uid,
        c_cn,
        c_givenname,
        c_sn,
        c_name,
        mail,
        c_o,
        c_telephonenumber
    FROM edulution_gal
    WHERE c_uid IN ($placeholders) OR mail IN ($placeholders)
");
$stmt->execute(array_merge($memberEmails, $memberEmails));
$memberRows = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Format for SOGo
$members = [];
foreach ($memberRows as $row) {
    $members[] = [
        'c_uid' => $row['c_uid'],
        'c_cn' => $row['c_cn'] ?: $row['c_uid'],
        'c_givenname' => $row['c_givenname'] ?: '',
        'c_sn' => $row['c_sn'] ?: '',
        'c_name' => $row['c_name'] ?: $row['c_uid'],
        'c_o' => $row['c_o'] ?: '',
        'c_telephonenumber' => $row['c_telephonenumber'] ?: '',
        'emails' => [
            [
                'value' => $row['mail'] ?: $row['c_uid'],
                'type' => 'work'
            ]
        ],
        'mail' => $row['mail'] ?: $row['c_uid']
    ];
}

echo json_encode(['members' => $members]);
?>
