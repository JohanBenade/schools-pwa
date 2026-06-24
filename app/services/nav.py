"""
Navigation helper - Generates consistent header across all pages
"""

def get_nav_header(title, back_url, back_label="Back", user_role=None):
    """
    Generate navigation header HTML.
    
    Args:
        title: Page title to display
        back_url: URL for back button
        back_label: Text for back button (default: "Back")
        user_role: User role for context-aware navigation
    
    Returns:
        HTML string for navigation header
    """
    from flask import session
    role = user_role or session.get('role')
    if back_label == 'Home' and role in ('principal', 'deputy', 'admin', 'management'):
        back_url = '/dashboard/'
        back_label = 'Dashboard'
    return f'''
    <nav class="nav-header">
        <a href="{back_url}" class="nav-back">← {back_label}</a>
        <span class="nav-title">{title}</span>
        <a href="/" class="nav-home">🏠</a>
    </nav>
    '''


def get_nav_styles():
    """Return CSS styles for navigation header."""
    return '''
    .nav-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 0;
        margin-bottom: 20px;
        border-bottom: 1px solid rgba(0,0,0,0.1);
    }
    .nav-back {
        color: #1E4FA0;  /* maragon-navy-accent (base.html --maragon-navy-accent) */
        text-decoration: none;
        font-size: 14px;
        font-weight: 500;
        padding: 8px 12px;
        border-radius: 8px;
        transition: background 0.2s;
    }
    .nav-back:hover {
        background: rgba(21, 51, 107, 0.08);
    }
    .nav-title {
        font-size: 18px;
        font-weight: 600;
        color: #15336B;  /* maragon-navy (base.html --maragon-navy) */
    }
    .nav-home {
        font-size: 20px;
        text-decoration: none;
        padding: 8px 12px;
        border-radius: 8px;
        transition: background 0.2s;
    }
    .nav-home:hover {
        background: rgba(0,0,0,0.05);
    }
    '''


def get_back_url(user_role, current_page=None):
    """Return (url, label) for the back link based on user role."""
    leadership_roles = ['principal', 'deputy', 'admin', 'management']
    if user_role in leadership_roles:
        return '/dashboard/', 'Dashboard'
    return '/', 'Home'


ROLE_LABELS = {
    'principal': 'Principal',
    'deputy': 'Deputy',
    'admin': 'Admin',
    'management': 'Management',
    'teacher': 'Teacher',
    'grade_head': 'Grade Head',
    'activities': 'Activities Coordinator',
    'sport_coordinator': 'Sport Coordinator',
    'office': 'Office',
}


def get_role_label(role):
    """Return human-readable label for a role."""
    return ROLE_LABELS.get(role, (role or '').replace('_', ' ').title())
