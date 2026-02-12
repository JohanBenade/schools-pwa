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
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }
    .nav-back {
        color: #60a5fa;
        text-decoration: none;
        font-size: 14px;
        font-weight: 500;
        padding: 8px 12px;
        border-radius: 8px;
        transition: background 0.2s;
    }
    .nav-back:hover {
        background: rgba(96, 165, 250, 0.1);
    }
    .nav-title {
        font-size: 18px;
        font-weight: 600;
        color: white;
    }
    .nav-home {
        font-size: 20px;
        text-decoration: none;
        padding: 8px 12px;
        border-radius: 8px;
        transition: background 0.2s;
    }
    .nav-home:hover {
        background: rgba(255,255,255,0.1);
    }
    /* Light theme version */
    .nav-header-light .nav-back { color: #2563eb; }
    .nav-header-light .nav-title { color: #1e293b; }
    .nav-header-light { border-bottom-color: rgba(0,0,0,0.1); }
    '''


def get_back_url(user_role, current_page):
    """
    Determine the correct back URL based on user role and current page.
    
    Leadership (principal, deputy, admin) → Dashboard for drill-downs
    Teachers → Home
    """
    # Leadership drill-down pages go back to Dashboard
    leadership_roles = ['principal', 'deputy', 'admin']
    dashboard_children = ['admin', 'overview', 'emergency-detail', 'absentees', 'class-detail']
    
    if user_role in leadership_roles and current_page in dashboard_children:
        return '/', 'Home'
    
    # Default: go home
    return '/', 'Home'
