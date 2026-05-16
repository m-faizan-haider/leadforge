from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class APIKeys(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    hunter_api_key = Column(String, default="")
    apollo_api_key = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)

class UserPersona(Base):
    __tablename__ = "personas"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) # E.g., "Senior Python Dev", "SEO Agency"
    objective = Column(String) # job_hunt, freelance, b2b_agency
    resume_text = Column(String, default="") # for job hunters
    skills = Column(String, default="") 
    value_proposition = Column(String, default="") # for agencies/startups
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True, index=True)
    name = Column(String, index=True)
    niche = Column(String)
    location = Column(String)
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    persona = relationship("UserPersona")
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), index=True)
    
    business_name = Column(String, index=True)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    website = Column(String)
    
    # Socials
    instagram = Column(String)
    facebook = Column(String)
    linkedin = Column(String)
    
    # Google Maps stats
    rating = Column(String)
    review_count = Column(Integer, default=0)
    
    # Tech
    tech_stack = Column(String)
    screenshot_path = Column(String)
    
    # Audits
    opportunity_score = Column(Integer, default=0)
    audit_findings = Column(JSON, default=dict)
    
    # AI Output
    email_draft = Column(String)
    pitch_angle_used = Column(String)
    
    status = Column(String, default="new", index=True) # new, emailed, replied, converted, skipped
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="leads")

class SMTPConfig(Base):
    __tablename__ = "smtp_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    host = Column(String, default="smtp.gmail.com")
    port = Column(Integer, default=587)
    username = Column(String)
    password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailLog(Base):
    __tablename__ = "email_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), index=True)
    
    step_number = Column(Integer, default=1)
    status = Column(String, default="sent") # sent, failed, opened, replied
    error_message = Column(String)
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    lead = relationship("Lead")
    campaign = relationship("Campaign")
