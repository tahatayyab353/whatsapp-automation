from app.schemas.common import (
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    PaginatedResponse,
    SystemInfoResponse,
)
from app.schemas.clinic import ClinicBase, ClinicRead, ClinicUpdate
from app.schemas.user import UserBase, UserRead
from app.schemas.membership import (
    ClinicMembershipBase,
    ClinicMembershipRead,
    MemberRead,
    MemberRoleUpdate,
)
from app.schemas.lead import LeadBase, LeadCreate, LeadRead, LeadUpdate
from app.schemas.conversation import (
    ConversationBase,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
)
from app.schemas.message import MessageBase, MessageCreate, MessageRead
from app.schemas.appointment import (
    AppointmentBase,
    AppointmentCreate,
    AppointmentRead,
    AppointmentUpdate,
)
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeDocumentBase,
    KnowledgeDocumentRead,
    KnowledgeUpdate,
)
from app.schemas.whatsapp import (
    WhatsAppAccountBase,
    WhatsAppAccountCreate,
    WhatsAppAccountRead,
    WhatsAppAccountUpdate,
)
from app.schemas.whatsapp_message import (
    WhatsAppContactItem,
    WhatsAppMessageItem,
    WhatsAppSendMessageResponse,
)
from app.schemas.whatsapp_webhook import (
    WebhookChange,
    WebhookEntry,
    WebhookMetadata,
    WebhookPayload,
    WebhookStatusResponse,
    WebhookValue,
)
from app.schemas.auth import (
    AuthenticatedTestResponse,
    ClinicContextTestResponse,
    LoginRequest,
    RoleTestResponse,
    TokenResponse,
)
from app.schemas.ai import AIChatRequest, AIChatResponse

__all__ = [
    "ErrorBody",
    "ErrorResponse",
    "HealthResponse",
    "MessageResponse",
    "PaginatedResponse",
    "SystemInfoResponse",
    "ClinicBase",
    "ClinicRead",
    "ClinicUpdate",
    "UserBase",
    "UserRead",
    "ClinicMembershipBase",
    "ClinicMembershipRead",
    "MemberRead",
    "MemberRoleUpdate",
    "LeadBase",
    "LeadCreate",
    "LeadRead",
    "LeadUpdate",
    "ConversationBase",
    "ConversationCreate",
    "ConversationRead",
    "ConversationUpdate",
    "MessageBase",
    "MessageCreate",
    "MessageRead",
    "AppointmentBase",
    "AppointmentCreate",
    "AppointmentRead",
    "AppointmentUpdate",
    "KnowledgeCreate",
    "KnowledgeDocumentBase",
    "KnowledgeDocumentRead",
    "KnowledgeUpdate",
    "WhatsAppAccountBase",
    "WhatsAppAccountCreate",
    "WhatsAppAccountRead",
    "WhatsAppAccountUpdate",
    "WhatsAppMessageItem",
    "WhatsAppContactItem",
    "WhatsAppSendMessageResponse",
    "WebhookPayload",
    "WebhookEntry",
    "WebhookChange",
    "WebhookValue",
    "WebhookMetadata",
    "WebhookStatusResponse",
    "LoginRequest",
    "TokenResponse",
    "AuthenticatedTestResponse",
    "ClinicContextTestResponse",
    "RoleTestResponse",
    "AIChatRequest",
    "AIChatResponse",
]
