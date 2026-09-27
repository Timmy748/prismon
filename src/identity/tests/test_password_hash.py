from identity.security.password_hasher import Argonid2Hasher


def test_should_generate_different_hashes_for_same_password(
    argon2_hasher: Argonid2Hasher,
):
    password = 'senha'

    hash_1 = argon2_hasher.hash(password)
    hash_2 = argon2_hasher.hash(password)

    assert hash_1 != hash_2


def test_should_verify_correct_password(argon2_hasher: Argonid2Hasher):
    password = 'senha'
    password_hash = argon2_hasher.hash(password)

    is_valid = argon2_hasher.verify(password, password_hash)

    assert is_valid is True


def test_should_verify_wrong_password(argon2_hasher: Argonid2Hasher):
    password = 'senha'
    password_hash = argon2_hasher.hash(password)

    is_valid = argon2_hasher.verify('diferente', password_hash)

    assert is_valid is False
