import hashlib
import os
import binascii

def hashear_password(password: str) -> str:
    """Genera un hash seguro para una contraseña utilizando PBKDF2."""
    salt = os.urandom(16)  # 128-bit salt
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return binascii.hexlify(salt).decode() + ':' + binascii.hexlify(key).decode()

def verificar_password(password: str, password_hash: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    try:
        salt_hex, key_hex = password_hash.split(':')
        salt = binascii.unhexlify(salt_hex)
        key = binascii.unhexlify(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
        return new_key == key
    except Exception as e:
        print(f"Error verificando contraseña: {e}")
        return False