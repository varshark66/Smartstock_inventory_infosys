// Global variables
let currentUser = null;
let notifications = [];

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    checkAuthentication();
    loadNotifications();
    setupMobileMenu();
}

// Setup event listeners
function setupEventListeners() {
    // Mobile menu toggle
    const menuToggle = document.querySelector('.menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', toggleMobileMenu);
    }

    // User dropdown
    const userDropdown = document.querySelector('.user-dropdown');
    if (userDropdown) {
        userDropdown.addEventListener('click', toggleUserDropdown);
    }

    // Notification icon
    const notificationIcon = document.querySelector('.notification-icon');
    if (notificationIcon) {
        notificationIcon.addEventListener('click', toggleNotifications);
    }

    // Logout button
    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        console.log('Logout button found:', logoutBtn);
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Logout button clicked!');
            logout();
        });
    } else {
        console.log('Logout button NOT found');
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.user-dropdown')) {
            closeUserDropdown();
        }
        if (!e.target.closest('.notification-icon')) {
            closeNotifications();
        }
    });
}

// Authentication check
function checkAuthentication() {
    const token = localStorage.getItem('token'); // Changed from 'authToken' to 'token'
    if (!token && !window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
        window.location.href = '/login';
        return;
    }
    
    if (token) {
        currentUser = {
            username: localStorage.getItem('username'),
            role: localStorage.getItem('role')
        };
    }
}

// Mobile menu functions
function setupMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    const menuToggle = document.querySelector('.menu-toggle');
    
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('active');
    }
}

function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('active');
}

// User dropdown functions
function toggleUserDropdown() {
    const dropdown = document.querySelector('.user-dropdown');
    dropdown.classList.toggle('active');
}

function closeUserDropdown() {
    const dropdown = document.querySelector('.user-dropdown');
    dropdown.classList.remove('active');
}

// Notification functions
function toggleNotifications() {
    const notificationPanel = document.querySelector('.notification-panel');
    if (notificationPanel) {
        notificationPanel.classList.toggle('active');
    }
}

function closeNotifications() {
    const notificationPanel = document.querySelector('.notification-panel');
    if (notificationPanel) {
        notificationPanel.classList.remove('active');
    }
}

function loadNotifications() {
    // Simulate loading notifications
    notifications = [
        {
            id: 1,
            type: 'success',
            title: 'Sale Completed',
            message: 'Order #1234 processed successfully',
            time: '10 min ago'
        },
        {
            id: 2,
            type: 'warning',
            title: 'Low Stock Alert',
            message: 'Product A is running low on stock',
            time: '1 hour ago'
        },
        {
            id: 3,
            type: 'info',
            title: 'System Update',
            message: 'New features added to inventory',
            time: '2 hours ago'
        }
    ];
    
    updateNotificationBadge();
}

function updateNotificationBadge() {
    const badge = document.querySelector('.notification-icon .badge');
    if (badge) {
        badge.textContent = notifications.length;
    }
}

// Logout function
function logout() {
    showLogoutDialog();
}

// Simple, clean, professional logout dialog
function showLogoutDialog() {
    // Create light dark blur overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(4px);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        animation: fadeIn 0.3s ease-out;
    `;

    // Create medium size dialog box
    const dialog = document.createElement('div');
    dialog.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 32px;
        width: 480px;
        max-width: 90vw;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        text-align: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        animation: slideUp 0.4s ease-out;
    `;

    dialog.innerHTML = `
        <!-- Warning Icon -->
        <div style="
            width: 48px;
            height: 48px;
            margin: 0 auto 20px;
            background: linear-gradient(135deg, #ff6b6b, #dc3545);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
        ">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="color: white;">
                <path d="M17 7l-1.41 1.41L15.17 9H17v2h-1.83l.59.59L17 14l1.41-1.41L18.83 12H17V9h1.83l-.59-.59L17 7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>

        <!-- Title -->
        <h3 style="
            color: #1a202c;
            margin: 0 0 12px 0;
            font-size: 20px;
            font-weight: 600;
            line-height: 1.4;
        ">Confirm Logout</h3>

        <!-- Message -->
        <p style="
            color: #4a5568;
            margin: 0 0 28px 0;
            font-size: 16px;
            line-height: 1.5;
        ">Are you sure you want to log out of the system?</p>

        <!-- Buttons -->
        <div style="
            display: flex;
            gap: 12px;
            justify-content: center;
        ">
            <button id="cancelBtn" style="
                padding: 14px 32px;
                border: 2px solid #e2e8f0;
                background: white;
                color: #6c757d;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
                min-width: 100px;
                outline: none;
            ">Cancel</button>

            <button id="logoutBtn" style="
                padding: 14px 32px;
                border: none;
                background: linear-gradient(135deg, #dc3545, #c82333);
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
                min-width: 100px;
                box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
                outline: none;
            ">Logout</button>
        </div>
    `;

    // Add smooth animations and hover effects
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        
        @keyframes slideUp {
            from { 
                opacity: 0;
                transform: translateY(30px) scale(0.9);
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        #cancelBtn:hover {
            background: #f8f9fa;
            border-color: #adb5bd;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        
        #logoutBtn:hover {
            background: linear-gradient(135deg, #c82333, #a02622);
            box-shadow: 0 6px 16px rgba(220, 53, 69, 0.4);
            transform: translateY(-2px);
        }
        
        #cancelBtn:active, #logoutBtn:active {
            transform: translateY(0) scale(0.98);
        }
        
        #cancelBtn:focus, #logoutBtn:focus {
            outline: 2px solid #007bff;
            outline-offset: 2px;
        }
    `;
    document.head.appendChild(style);

    // Add to page first
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Wait a moment for DOM to be ready, then add event listeners
    setTimeout(() => {
        const cancelBtn = document.getElementById('cancelBtn');
        const logoutBtn = document.getElementById('logoutBtn');
        
        if (cancelBtn && logoutBtn) {
            // Event listeners
            cancelBtn.addEventListener('click', () => {
                overlay.style.animation = 'fadeOut 0.3s ease-in';
                setTimeout(() => {
                    document.body.removeChild(overlay);
                    document.head.removeChild(style);
                }, 300);
            });

            logoutBtn.addEventListener('click', () => {
                localStorage.removeItem('token');
                localStorage.removeItem('role');
                localStorage.removeItem('username');
                window.location.href = '/login';
            });
        } else {
            console.error('Dialog buttons not found:', { cancelBtn, logoutBtn });
        }
    }, 100);

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.style.animation = 'fadeOut 0.3s ease-in';
            setTimeout(() => {
                document.body.removeChild(overlay);
                document.head.removeChild(style);
            }, 300);
        }
    });

    // Add to page
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
}

// Utility functions
function showAlert(message, type = 'info', duration = 3000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Find the best place to insert the alert
    const container = document.querySelector('.page-content') || 
                     document.querySelector('.dashboard-container') || 
                     document.querySelector('.products-container') ||
                     document.body;
    
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto remove after duration
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, duration);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// API helper functions
async function apiRequest(url, options = {}) {
    const token = localStorage.getItem('token'); // Changed from 'authToken' to 'token'
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };
    
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    try {
        const response = await fetch(url, finalOptions);
        
        if (response.status === 401) {
            localStorage.removeItem('token'); // Changed from 'authToken' to 'token'
            localStorage.removeItem('role');
            localStorage.removeItem('username');
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        showAlert('An error occurred. Please try again.', 'danger');
        throw error;
    }
}

// Loading states
function showLoading(element) {
    element.disabled = true;
    element.innerHTML = '<span class="loading"></span> Loading...';
}

function hideLoading(element, originalText) {
    element.disabled = false;
    element.innerHTML = originalText;
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Export functions to global scope
window.dashboardApp = {
    showAlert,
    formatCurrency,
    formatDate,
    formatTime,
    apiRequest,
    showLoading,
    hideLoading,
    validateForm,
    toggleMobileMenu,
    logout
};

// Handle window resize
window.addEventListener('resize', function() {
    if (window.innerWidth > 768) {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.remove('active');
        }
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const modalInstance = bootstrap.Modal.getInstance(modal);
            if (modalInstance) {
                modalInstance.hide();
            }
        });
    }
});

// Auto-refresh functionality
function setupAutoRefresh(interval = 60000) {
    setInterval(async function() {
        // Refresh dashboard stats if on dashboard page
        if (window.location.pathname === '/dashboard') {
            try {
                const response = await apiRequest('/api/dashboard/stats');
                if (response) {
                    updateDashboardStats(response);
                }
            } catch (error) {
                console.error('Auto-refresh failed:', error);
            }
            function updateThresholdForCategory() {
    const category = document.getElementById('productCategory').value;
    const minStockInput = document.getElementById('minStockLevel');
    const thresholds = {
        "Electronics": 5,
        "Food": 20,
        "Beverages": 15,
        "Clothing": 10,
        "Furniture": 3,
        "Books": 25,
        "Toys": 15,
        "Sports": 8,
        "Beauty": 12,
        "Health": 10,
        "Office": 15,
        "Cleaning": 20,
        "Other": 10
    };
    
    if (thresholds[category]) {
        minStockInput.value = thresholds[category];
    }
    // Load real alerts from database
async function loadAlerts() {
    try {
        const response = await fetch('/api/alerts');
        const data = await response.json();
        const alerts = data.alerts || [];
        
        // Display alerts in table
        displayAlerts(alerts);
        
        // Update statistics
        updateAlertStats(alerts);
        
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

// Display alerts in table
function displayAlerts(alerts) {
    const tbody = document.querySelector('#alertsTable tbody');
    if (!tbody) return;
    
    if (alerts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No alerts found</td></tr>';
        return;
    }
    
    tbody.innerHTML = alerts.map(alert => `
        <tr data-priority="${alert.priority}" data-type="${alert.alert_type}" data-status="${alert.status}">
            <td><input type="checkbox" class="alert-checkbox"></td>
            <td>
                <span class="badge bg-${alert.priority === 'critical' ? 'danger' : alert.priority === 'high' ? 'warning' : 'info'}">
                    ${alert.priority.toUpperCase()}
                </span>
            </td>
            <td>${alert.alert_type.replace('_', ' ').toUpperCase()}</td>
            <td>${alert.message}</td>
            <td>${alert.product_name || 'N/A'}</td>
            <td>
                <span class="badge bg-${alert.status === 'active' ? 'warning' : alert.status === 'acknowledged' ? 'success' : 'secondary'}">
                    ${alert.status}
                </span>
            </td>
            <td>${new Date(alert.created_at).toLocaleString()}</td>
            <td>
                <button class="btn btn-sm btn-outline-success" onclick="resolveAlert('${alert._id}')" ${alert.status !== 'active' ? 'disabled' : ''}>
                    <i class="fas fa-check"></i> Resolve
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="dismissAlert('${alert._id}')" ${alert.status !== 'active' ? 'disabled' : ''}>
                    <i class="fas fa-times"></i> Dismiss
                </button>
            </td>
        </tr>
    `).join('');
}

// Update alert statistics
function updateAlertStats(alerts) {
    const critical = alerts.filter(a => a.priority === 'critical').length;
    const active = alerts.filter(a => a.status === 'active').length;
    const today = alerts.filter(a => 
        new Date(a.created_at).toDateString() === new Date().toDateString()
    ).length;
    
    // Update DOM elements
    const criticalElement = document.getElementById('critical-alerts');
    const activeElement = document.getElementById('active-alerts');
    const todayElement = document.getElementById('today-alerts');
    
    if (criticalElement) criticalElement.textContent = critical;
    if (activeElement) activeElement.textContent = active;
    if (todayElement) todayElement.textContent = today;
}

// Load alerts when page loads
document.addEventListener('DOMContentLoaded', loadAlerts);

// Auto-refresh alerts every 30 seconds
setInterval(loadAlerts, 30000);
}
        }
    }, interval);
}

function updateDashboardStats(stats) {
    // Update dashboard statistics
    const elements = {
        'total-products': stats.total_products,
        'total-stock': stats.total_stock,
        'low-stock-items': stats.low_stock_items,
        'today-sales': stats.today_sales,
        'total-transactions': stats.total_transactions
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

// Initialize auto-refresh
setupAutoRefresh();
