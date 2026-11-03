"""
Configuración de la aplicación.

En vez de escribir claves y direcciones directamente en el código, las leemos
de "variables de entorno" (o del archivo .env). Así el mismo código funciona
en tu PC y en el servidor, cambiando solo la configuración.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "clave-de-desarrollo-no-usar-en-produccion"


class Settings(BaseSettings):
    # Cada atributo es una variable de configuración con su valor por defecto.
    # Si existe en el .env (ej: SECRET_KEY=...), ese valor reemplaza al de acá.
    app_name: str = "VaultBase"
    app_env: str = "development"  # "production" en el servidor
    secret_key: str = DEV_SECRET
    database_url: str = "sqlite:///./vaultbase.db"
    access_token_expire_minutes: int = 60 * 24  # 1 día
    # Emails de los administradores, separados por coma (ej: "yo@mail.com").
    # Pueden ver estadísticas de uso, generar links para restablecer contraseñas
    # y ver los datos de quien haya aceptado compartirlos.
    admin_emails: str = ""

    # Le indicamos a pydantic-settings que lea el archivo .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _ajustes_de_produccion(self):
        # Los proveedores (Neon, Render) dan la URL como "postgres://..." o
        # "postgresql://...". SQLAlchemy necesita saber qué driver usar, así
        # que la convertimos a "postgresql+psycopg://...".
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + self.database_url[len(prefix):]
        # En producción, arrancar con la clave de desarrollo sería un agujero
        # de seguridad (cualquiera podría fabricar tokens). Mejor no arrancar.
        if self.app_env == "production" and (self.secret_key == DEV_SECRET or len(self.secret_key) < 32):
            raise ValueError("En producción, SECRET_KEY debe ser una clave propia de al menos 32 caracteres")
        return self

    def is_admin(self, email: str) -> bool:
        admins = {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}
        return email.lower() in admins

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache  # guarda el resultado: el .env se lee una sola vez
def get_settings() -> Settings:
    return Settings()
