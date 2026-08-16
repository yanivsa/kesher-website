#!/usr/bin/env python3
import base64
import sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBLIC_KEY = b'''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAorxXsZ5dFXSWOBLf+z3o
q26YLf0SvzXRzFsfF23S3qwIkPeHM4kKKb8KtvG5sqTz9xt9tkaHbwZhFr0qiP+t
ir83s3zuWug1AL8CsyIOn8ng2RfhEJvsMQk47fdv8oGXUEpE1Xy6YZHI3AFKCH2E
THVzUtIVJZgYySOMXbj7oAJdTMDxPRQneS3qJ5k8kkmtZAkQyX/VnZfITAslQCex
gNt9E2IIXk7h4OiCOnOPEIbETW2orSHoM+aODdb5y3xQGZxdavVAOcH9bMvrQsEV
MBanGT7kXLulb6VW6nLx7BX00Za4jwu5/VhpwiGF836DoTA29dwioI7HpoIJj9ZO
xQIDAQAB
-----END PUBLIC KEY-----
'''

value = sys.stdin.read().strip()
if not value:
    raise SystemExit("empty value")
key = serialization.load_pem_public_key(PUBLIC_KEY)
cipher = key.encrypt(
    value.encode(),
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    ),
)
print(base64.b64encode(cipher).decode())
