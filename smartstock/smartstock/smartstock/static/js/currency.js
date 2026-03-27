// Global Currency Management System
class CurrencyManager {
    constructor() {
        this.currencySymbols = {
            'INR': '₹',
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CAD': 'C$',
            'AUD': 'A$',
            'CHF': 'CHF',
            'CNY': '¥',
            'SEK': 'kr'
        };
        
        this.exchangeRates = {};
        this.baseCurrency = 'INR';
        this.currentCurrency = 'INR';
        this.init();
    }
    
    init() {
        // Load saved currency from localStorage
        const savedCurrency = localStorage.getItem('selectedCurrency') || 'INR';
        this.setCurrentCurrency(savedCurrency);
        
        // Load exchange rates if needed
        this.loadExchangeRates();
        
        // Listen for currency change events
        document.addEventListener('currencyChanged', (e) => {
            this.setCurrentCurrency(e.detail.currency);
        });
        
        // Auto-update exchange rates every hour
        setInterval(() => this.loadExchangeRates(), 3600000);
    }
    
    setCurrentCurrency(currency) {
        this.currentCurrency = currency;
        window.currentCurrency = currency;
        window.currentCurrencySymbol = this.currencySymbols[currency];
        
        // Save to localStorage
        localStorage.setItem('selectedCurrency', currency);
        localStorage.setItem('selectedCurrencySymbol', this.currencySymbols[currency]);
        
        // Update all currency displays on the page
        this.updateAllCurrencyDisplays();
    }
    
    formatCurrency(amount, currency = null) {
        const targetCurrency = currency || this.currentCurrency;
        const symbol = this.currencySymbols[targetCurrency] || '₹';
    
        let convertedAmount = amount;

        // ✅ ALWAYS convert if currency is different
        if (targetCurrency !== this.baseCurrency) {
            convertedAmount = this.convertCurrency(amount, this.baseCurrency, targetCurrency);
        }

        return `${symbol}${parseFloat(convertedAmount).toFixed(2)}`;
    }
    
    convertCurrency(amount, fromCurrency, toCurrency) {
        if (fromCurrency === toCurrency) return amount;
        
        // If we don't have exchange rates, return original amount
        if (!this.exchangeRates[fromCurrency] || !this.exchangeRates[toCurrency]) {
            console.warn(`Exchange rates not available for ${fromCurrency} to ${toCurrency}`);
            return amount;
        }
        
        // Convert through base currency
        const amountInBase = amount / this.exchangeRates[fromCurrency];
        const convertedAmount = amountInBase * this.exchangeRates[toCurrency];
        
        return convertedAmount;
    }
    
    updateAllCurrencyDisplays() {
        // Update all currency symbols
        document.querySelectorAll('.currency-symbol, [data-currency-symbol]').forEach(element => {
            element.textContent = this.currencySymbols[this.currentCurrency] || '₹';
        });
        
        // Update all price displays
        document.querySelectorAll('.price-display, .amount, .total-amount, .price, .cost').forEach(element => {
            const basePrice = element.getAttribute('data-base-price') || element.textContent;
            if (basePrice) {
                const numericPrice = parseFloat(basePrice.replace(/[^0-9.-]/g, ''));
                if (!isNaN(numericPrice)) {
                    element.textContent = this.formatCurrency(numericPrice);
                }
            }
        });
        
        // Update any element with currency attribute
        document.querySelectorAll('[data-currency]').forEach(element => {
            element.setAttribute('data-currency', this.currentCurrency);
        });
        
        console.log(`Currency updated to: ${this.currentCurrency} (${this.currencySymbols[this.currentCurrency]})`);
    }
    
    async loadExchangeRates() {
        try {
            // Try to fetch real exchange rates from a free API
            const response = await fetch('https://api.exchangerate-api.com/v4/latest/INR');
            
            if (response.ok) {
                const data = await response.json();
                this.exchangeRates = data.rates;
                console.log('Real-time exchange rates loaded:', this.exchangeRates);
                
                // Save to localStorage for offline use
                localStorage.setItem('exchangeRates', JSON.stringify(this.exchangeRates));
                localStorage.setItem('exchangeRatesTimestamp', new Date().toISOString());
            } else {
                throw new Error('API request failed');
            }
        } catch (error) {
            console.warn('Failed to fetch real exchange rates, using fallback rates:', error);
            
            // Fallback to fixed exchange rates if API fails
            this.exchangeRates = {
                'INR': 1.0,
                'USD': 0.012,
                'EUR': 0.011,
                'GBP': 0.0095,
                'JPY': 1.8,
                'CAD': 0.016,
                'AUD': 0.018,
                'CHF': 0.0105,
                'CNY': 0.087,
                'SEK': 0.12
            };
            
            // Try to load cached rates from localStorage
            const cachedRates = localStorage.getItem('exchangeRates');
            const cachedTimestamp = localStorage.getItem('exchangeRatesTimestamp');
            
            if (cachedRates && cachedTimestamp) {
                const cacheAge = new Date() - new Date(cachedTimestamp);
                const cacheAgeHours = cacheAge / (1000 * 60 * 60);
                
                // Use cached rates if less than 24 hours old
                if (cacheAgeHours < 24) {
                    try {
                        this.exchangeRates = JSON.parse(cachedRates);
                        console.log('Using cached exchange rates:', this.exchangeRates);
                    } catch (e) {
                        console.warn('Failed to parse cached rates, using fallback');
                    }
                }
            }
        }
    }
    
    getCurrencySymbol(currency = null) {
        const targetCurrency = currency || this.currentCurrency;
        return this.currencySymbols[targetCurrency] || '₹';
    }
    
    getAvailableCurrencies() {
        return Object.keys(this.currencySymbols).map(code => ({
            code: code,
            symbol: this.currencySymbols[code],
            name: this.getCurrencyName(code)
        }));
    }
    
    getCurrencyName(code) {
        const names = {
            'INR': 'Indian Rupee',
            'USD': 'US Dollar',
            'EUR': 'Euro',
            'GBP': 'British Pound',
            'JPY': 'Japanese Yen',
            'CAD': 'Canadian Dollar',
            'AUD': 'Australian Dollar',
            'CHF': 'Swiss Franc',
            'CNY': 'Chinese Yuan',
            'SEK': 'Swedish Krona'
        };
        return names[code] || code;
    }
}

// Initialize global currency manager
window.currencyManager = new CurrencyManager();

// Helper functions for backward compatibility
function formatCurrency(amount, currency) {
    return window.currencyManager.formatCurrency(amount, currency);
}

function updateGlobalCurrency(currency) {
    window.currencyManager.setCurrentCurrency(currency);
}

function getCurrencySymbol(currency) {
    return window.currencyManager.getCurrencySymbol(currency);
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CurrencyManager;
}
