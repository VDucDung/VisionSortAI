INSERT INTO accounts (id, phone, email, full_name, password_hash, role, is_active, token_version)
VALUES (1, '0901234567', 'old-user@example.com', 'Existing email owner', 'unchanged-test-hash', 'USER', TRUE, 0);
INSERT INTO accounts (id, phone, email, full_name, password_hash, role, is_active, token_version)
VALUES (2, '0901234568', 'another-user@example.com', 'Existing phone owner', 'unchanged-test-hash', 'USER', TRUE, 0);
