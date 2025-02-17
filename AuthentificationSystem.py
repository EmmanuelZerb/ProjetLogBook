import sqlite3
import hashlib
import os

class AuthenticationSystem:
    def __init__(self, db_name='users.db'):
        self.db_name = db_name
        self.setup_database()
        self.create_default_user()

    def setup_database(self):
        """Initialise la base de données et crée la table users si elle n'existe pas"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_default_user(self):
        """Crée l'utilisateur par défaut s'il n'existe pas"""
        try:
            self.add_user("user", "mdp")
        except sqlite3.IntegrityError:
            pass  # L'utilisateur existe déjà

    def add_user(self, username, password):
        """Ajoute un nouvel utilisateur à la base de données"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Hash du mot de passe pour plus de sécurité
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                      (username, hashed_password))
        
        conn.commit()
        conn.close()

    def authenticate(self, username, password):
        """Authentifie un utilisateur"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Hash du mot de passe pour la comparaison
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                      (username, hashed_password))
        
        user = cursor.fetchone()
        conn.close()
        
        return user is not None

    def login_prompt(self):
        """Interface en ligne de commande pour l'authentification"""
        while True:
            username = input("Nom d'utilisateur: ")
            password = input("Mot de passe: ")

            if self.authenticate(username, password):
                print("Connexion réussie!")
                return True
            else:
                print("Échec de l'authentification. Veuillez réessayer.")
                retry = input("Voulez-vous réessayer? (o/n): ")
                if retry.lower() != 'o':
                    return False

def main():
    auth_system = AuthenticationSystem()
    auth_system.login_prompt()

if __name__ == "__main__":
    main()