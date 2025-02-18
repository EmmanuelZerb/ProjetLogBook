<?php
session_start();
require_once "../classes/Auth.php";

$error = null;

// Traitement de la déconnexion
if(isset($_GET['logout'])) {
    Auth::logout();
    header('Location: index.php');
    exit();
}

// Traitement de la connexion
if($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';

    if(Auth::login($username, $password)) {
        header('Location: index.php');
        exit();
    } else {
        $error = "Identifiants incorrects";
    }
}
?>
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Espace Professeur</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container">
        <?php if(!Auth::isLoggedIn()): ?>
            <!-- Formulaire de connexion -->
            <div class="form-container">
                <h1>Connexion Professeur</h1>
                
                <?php if($error): ?>
                    <div class="alert alert-error">
                        <?php echo htmlspecialchars($error); ?>
                    </div>
                <?php endif; ?>

                <form method="POST">
                    <div class="form-group">
                        <label for="username">Nom d'utilisateur</label>
                        <input type="text" id="username" name="username" required>
                    </div>

                    <div class="form-group">
                        <label for="password">Mot de passe</label>
                        <input type="password" id="password" name="password" required>
                    </div>

                    <button type="submit" class="btn">Se connecter</button>
                </form>
            </div>
        <?php else: ?>
            <!-- Page d'accueil connectée -->
            <?php $user = Auth::getUser(); ?>
            <div class="welcome-container">
                <h1>Bienvenue <?php echo htmlspecialchars($user->getNomComplet()); ?></h1>
                <p>Vous êtes connecté en tant que professeur.</p>
                <a href="?logout=1" class="btn btn-logout">Se déconnecter</a>
            </div>
        <?php endif; ?>
    </div>
</body>
</html>