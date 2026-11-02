"""
Configuración de la aplicación.

En vez de escribir claves y direcciones directamente en el código, las leemos
de "variables de entorno" (o del archivo .env). Así el mismo código funciona
en tu PC y en el servidor, cambiando solo la configuración.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Cada atributo es una variable de configuración con su valor por defecto.
    # Si existe en el .env (ej: SECRET_KEY=...), ese valor reemplaza al de acá.
    app_name: str = "VaultBase"
    secret_key: str = "clave-de-desarrollo-no-usar-en-produccion"
    database_url: str = "sqlite:///./vaultbase.db"
    access_token_expire_minutes: int = 60 * 24  # 1 día

    # Le indicamos a pydantic-settings que lea el archivo .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache  # guarda el resultado: el .env se lee una sola vez
def get_settings() -> Settings:
    return Settings()
