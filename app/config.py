import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    
    # Notion API
    NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
    
    # Tenant configuration (resolved at runtime from S_Tenant)
    # For MVP, hardcode Maragon tenant ID
    DEFAULT_TENANT_ID = "MARAGON-001"
    
    # Database IDs for Maragon (from S_Tenant record)
    # These would normally be fetched from S_Tenant at runtime
    NOTION_DB_STAFF = os.environ.get("NOTION_DB_STAFF", "2dbb2e800029802db193c5d059431a9f")
    NOTION_DB_LEARNER = os.environ.get("NOTION_DB_LEARNER", "2dbb2e800029806e800ad986037e21d4")
    NOTION_DB_MENTOR_GROUP = os.environ.get("NOTION_DB_MENTOR_GROUP", "2dbb2e8000298055922ef7b0349f6181")
    NOTION_DB_ATTENDANCE = os.environ.get("NOTION_DB_ATTENDANCE", "2dbb2e80002980308500f81c534665d3")
    NOTION_DB_ATTENDANCE_ENTRY = os.environ.get("NOTION_DB_ATTENDANCE_ENTRY", "2dbb2e8000298046ad78c791ef0d63fb")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
