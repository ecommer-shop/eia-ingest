"""Autenticación JWT (HS256) para endpoints de la API y webhooks."""
from __future__ import annotations

import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eia_ingest.config import JWT_ALGORITHM, JWT_SECRET

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def require_valid_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Dependencia que valida `Authorization: Bearer <jwt>`.

    Verifica firma (HS256 con JWT_SECRET) y expiración (exp).
    Retorna el payload decodificado del token.

    Raises:
        HTTPException 401: token ausente, secreto no configurado,
            firma inválida o token expirado.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token faltante. Usa 'Authorization: Bearer <jwt>'.",
            headers=_AUTH_HEADERS,
        )

    if not JWT_SECRET:
        logger.error("JWT_SECRET no está configurado; rechazando request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación no configurada en el servidor.",
            headers=_AUTH_HEADERS,
        )

    try:
        return jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers=_AUTH_HEADERS,
        )
    except jwt.InvalidTokenError:
        logger.warning("JWT inválido recibido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers=_AUTH_HEADERS,
        )
