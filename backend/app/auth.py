from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from fastapi import Depends, Header, HTTPException, status
from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


class SupabaseAuth:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        self.required = os.getenv("PRIVA_AUTH_REQUIRED", "false").lower() == "true"
        self.session = requests

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key)

    def user_from_token(self, token: str) -> AuthenticatedUser | None:
        if not self.configured:
            return None
        try:
            response = self.session.get(
                f"{self.url}/auth/v1/user",
                headers={"apikey": self.anon_key, "Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if response.status_code != 200:
                return None
            payload = response.json()
            user_id = payload.get("id")
            return AuthenticatedUser(str(user_id), payload.get("email")) if user_id else None
        except (requests.RequestException, ValueError):
            return None

    def current_user(self, authorization: str | None) -> AuthenticatedUser:
        if not authorization:
            if self.required and self.configured:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
            return AuthenticatedUser("local-development")

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            if self.required and self.configured:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
            return AuthenticatedUser("local-development")

        if self.configured:
            user = self.user_from_token(token)
            if user is not None:
                return user

        if self.required and self.configured:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase session")
        return AuthenticatedUser("local-development")


supabase_auth = SupabaseAuth()


def current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    return supabase_auth.current_user(authorization)


class UserCredentialVault:
    def __init__(self) -> None:
        key = os.getenv("PRIVA_CREDENTIAL_ENCRYPTION_KEY", "")
        self.fernet = None
        self._configuration_error: str | None = None
        if key:
            try:
                self.fernet = Fernet(key.encode())
            except (ValueError, TypeError):
                self._configuration_error = (
                    "PRIVA_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key"
                )
        self._credentials: dict[str, bytes] = {}

    @property
    def configured(self) -> bool:
        return self.fernet is not None

    def put(self, user_id: str, values: dict[str, str]) -> None:
        if self.fernet is None:
            message = self._configuration_error or "PRIVA_CREDENTIAL_ENCRYPTION_KEY is required"
            raise RuntimeError(message)
        encoded = "\n".join(f"{key}={values[key]}" for key in ("api_key", "api_secret", "passphrase"))
        self._credentials[user_id] = self.fernet.encrypt(encoded.encode())

    def get(self, user_id: str) -> dict[str, str] | None:
        if self.fernet is None or user_id not in self._credentials:
            return None
        try:
            values = {}
            for line in self.fernet.decrypt(self._credentials[user_id]).decode().splitlines():
                key, _, value = line.partition("=")
                values[key] = value
            return values
        except (InvalidToken, UnicodeDecodeError):
            return None

    def delete(self, user_id: str) -> None:
        self._credentials.pop(user_id, None)

    def export(self, user_id: str) -> str | None:
        value = self._credentials.get(user_id)
        return value.decode() if value else None

    def import_encrypted(self, user_id: str, value: str) -> bool:
        if self.fernet is None:
            return False
        try:
            self.fernet.decrypt(value.encode())
        except (InvalidToken, ValueError):
            return False
        self._credentials[user_id] = value.encode()
        return True


credential_vault = UserCredentialVault()
