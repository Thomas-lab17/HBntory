CREATE TABLE users{
    
    id INTEGER NOT NULL PRIMARY KEY UNIQUE;
    username STRING NOT NULL;
    password_hash STRING NOT NULL;
    role STRING NOT NULL;
    branch_id INTEGER NOT NULL FOREIGN KEY;
    is_active BOOLEAN NOT NULL;
    created_at TIMESTAMP NOT NULL;
    updated_at TIMESTAMP NOT NULL;
};