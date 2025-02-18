<?php
require_once "../models/MonPDO.php";

class User {
    private $id;
    private $username;
    private $nom;
    private $prenom;

    public function __construct($donnees) {
        $this->id = $donnees['id'];
        $this->username = $donnees['username'];
        $this->nom = $donnees['nom'];
        $this->prenom = $donnees['prenom'];
    }

    public function getId() { return $this->id; }
    public function getUsername() { return $this->username; }
    public function getNom() { return $this->nom; }
    public function getPrenom() { return $this->prenom; }
    
    public function getNomComplet() {
        return $this->prenom . " " . $this->nom;
    }
}