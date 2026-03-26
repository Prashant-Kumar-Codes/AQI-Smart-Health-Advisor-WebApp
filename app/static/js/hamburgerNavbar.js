/*
 * Universal Hamburger Navigation Menu
 * Handles mobile navigation toggle and interactions for any page
 * 
 * Usage:
 * 1. Include this script in your page
 * 2. Ensure your HTML has elements with classes: .hamburger and .nav-links
 * 3. (Optional) Customize settings by passing config object
 * 
 * Example:
 * <script src="hamburgerNav.js"></script>
 * <script>
 *   // Use default settings
 *   const nav = new HamburgerNav();
 *   
 *   // OR customize settings
 *   const nav = new HamburgerNav({
 *     hamburgerSelector: '.hamburger',
 *     navLinksSelector: '.nav-links',
 *     navLinkSelector: '.nav-link',
 *     breakpoint: 768,
 *     menuWidth: '60%',
 *     enableBodyScroll: false,
 *     onOpen: () => console.log('Menu opened'),
 *     onClose: () => console.log('Menu closed')
 *   });
 * </script>
 */

// Only create if not already defined (prevents duplicate errors)
if (typeof window.HamburgerNav === 'undefined') {
    
    window.HamburgerNav = class HamburgerNav {
        constructor(config = {}) {
            // Default configuration
            this.config = {
                hamburgerSelector: '.hamburger',
                navLinksSelector: '.nav-links',
                navLinkSelector: '.nav-link',
                breakpoint: 768,
                menuWidth: '60%',
                enableBodyScrollLock: false,
                closeOnLinkClick: true,
                closeOnOutsideClick: true,
                closeOnEscape: true,
                closeOnResize: true,
                animationDuration: 300,
                onOpen: null,
                onClose: null,
                onToggle: null,
                ...config
            };

            this.hamburger = null;
            this.navLinks = null;
            this.isOpen = false;
            this.init();
        }

        init() {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setup());
            } else {
                this.setup();
            }
        }

        setup() {
            this.hamburger = document.querySelector(this.config.hamburgerSelector);
            this.navLinks = document.querySelector(this.config.navLinksSelector);

            if (!this.hamburger || !this.navLinks) {
                console.warn(`Hamburger menu elements not found. Looking for: ${this.config.hamburgerSelector} and ${this.config.navLinksSelector}`);
                return;
            }

            this.attachEventListeners();
            
            // Apply custom menu width if specified
            if (this.config.menuWidth !== '60%') {
                this.applyCustomWidth();
            }
        }

        applyCustomWidth() {
            const style = document.createElement('style');
            style.textContent = `
                @media (max-width: ${this.config.breakpoint}px) {
                    ${this.config.navLinksSelector} {
                        width: ${this.config.menuWidth};
                        left: -${this.config.menuWidth};
                    }
                    ${this.config.navLinksSelector}::before {
                        left: ${this.config.menuWidth};
                        width: calc(100% - ${this.config.menuWidth});
                    }
                }
            `;
            document.head.appendChild(style);
        }

        attachEventListeners() {
            // Toggle menu on hamburger click
            this.hamburger.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMenu();
            });

            // Close menu when clicking on nav links
            if (this.config.closeOnLinkClick) {
                const links = this.navLinks.querySelectorAll(this.config.navLinkSelector);
                links.forEach(link => {
                    link.addEventListener('click', () => {
                        this.closeMenu();
                    });
                });
            }

            // Close menu when clicking on overlay
            if (this.config.closeOnOutsideClick) {
                // Create and manage overlay click separately
                document.addEventListener('click', (e) => {
                    const navRect = this.navLinks.getBoundingClientRect();
                    if (this.isOpen && window.innerWidth <= this.config.breakpoint) {
                        // Check if click is outside the nav menu (on the overlay area)
                        if (e.clientX > navRect.right) {
                            this.closeMenu();
                        }
                    }
                });
            }

            // Close menu on escape key
            if (this.config.closeOnEscape) {
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape' && this.isOpen) {
                        this.closeMenu();
                    }
                });
            }

            // Handle window resize
            if (this.config.closeOnResize) {
                window.addEventListener('resize', () => {
                    if (window.innerWidth > this.config.breakpoint && this.isOpen) {
                        this.closeMenu();
                    }
                });
            }
        }

        toggleMenu() {
            if (this.isOpen) {
                this.closeMenu();
            } else {
                this.openMenu();
            }

            // Trigger onToggle callback
            if (typeof this.config.onToggle === 'function') {
                this.config.onToggle(this.isOpen);
            }
        }

        openMenu() {
            this.hamburger.classList.add('active');
            this.navLinks.classList.add('active');
            this.isOpen = true;
            
            // Prevent body scroll if enabled
            if (this.config.enableBodyScrollLock) {
                document.body.style.overflow = 'hidden';
            }

            // Trigger onOpen callback
            if (typeof this.config.onOpen === 'function') {
                this.config.onOpen();
            }
        }

        closeMenu() {
            this.hamburger.classList.remove('active');
            this.navLinks.classList.remove('active');
            this.isOpen = false;
            
            // Re-enable body scroll
            if (this.config.enableBodyScrollLock) {
                document.body.style.overflow = '';
            }

            // Trigger onClose callback
            if (typeof this.config.onClose === 'function') {
                this.config.onClose();
            }
        }

        // Public API methods
        open() {
            if (!this.isOpen) {
                this.openMenu();
            }
        }

        close() {
            if (this.isOpen) {
                this.closeMenu();
            }
        }

        toggle() {
            this.toggleMenu();
        }

        destroy() {
            // Remove event listeners and clean up
            this.closeMenu();
            // Note: For complete cleanup, you'd need to store references to all event listeners
            console.log('HamburgerNav instance destroyed');
        }
    };
    
    // Auto-initialize with default settings (can be disabled by setting window.autoInitHamburger = false)
    if (window.autoInitHamburger !== false) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                window.hamburgerNav = new window.HamburgerNav();
                console.log('✅ HamburgerNav loaded');
            });
        } else {
            window.hamburgerNav = new window.HamburgerNav();
            console.log('✅ HamburgerNav loaded');
        }
    }
    
} else {
    console.log('ℹ️ HamburgerNav already exists');
}