<?php
require_once "../models/MonPDO.php";
require_once "User.php";

class Auth {
    public static function login($username, $password) {
        $pdo = MonPDO::getPDO();
        $req = "SELECT * FROM prof WHERE username = :username AND password = :password";
        $stmt = $pdo->prepare($req);
        $stmt->execute([
            'username' => $username,
            'password' => $password
        ]);
        
        if($userData = $stmt->fetch()) {
            $_SESSION['user_id'] = $userData['id'];
            return true;
        }
        return false;
    }

    public static function isLoggedIn() {
        return isset($_SESSION['user_id']);
    }

    public static function getUser() {
        if(!isset($_SESSION['user_id'])) return false;
        
        $pdo = MonPDO::getPDO();
        $req = "SELECT * FROM prof WHERE id = :id";
        $stmt = $pdo->prepare($req);
        $stmt->execute(['id' => $_SESSION['user_id']]);
        
        if($userData = $stmt->fetch()) {
            return new User($userData);
        }
        return false;
    }

    public static function logout() {
        unset($_SESSION['user_id']);
        session_destroy();
    }

    public static function requireAuth() {
        if(!self::isLoggedIn()) {
            header('Location: index.php');
            exit();
        }
    }
}