// Vita API Client — connects frontend to Flask backend
var API_BASE = 'http://127.0.0.1:5050/api';
var currentUser = JSON.parse(localStorage.getItem('vita_user') || 'null');
var userToken = localStorage.getItem('vita_token') || '';

function api(path, options) {
    options = options || {};
    options.headers = options.headers || {};
    if (userToken) options.headers['Authorization'] = userToken;
    if (options.body && typeof options.body === 'object') {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }
    return fetch(API_BASE + path, options).then(function(r) { return r.json(); });
}

// ==================== AUTH UI ====================

function showAuthModal(mode) {
    document.getElementById('authModal').style.display = 'flex';
    document.getElementById('authTitle').setAttribute('data-sq', mode === 'login' ? 'Hyr' : 'Regjistrohu');
    document.getElementById('authTitle').setAttribute('data-en', mode === 'login' ? 'Sign In' : 'Register');
    document.getElementById('authTitle').textContent = mode === 'login' ? 'Hyr' : 'Regjistrohu';
    document.getElementById('authSubmit').setAttribute('data-sq', mode === 'login' ? 'Hyr' : 'Krijo Llogari');
    document.getElementById('authSubmit').setAttribute('data-en', mode === 'login' ? 'Sign In' : 'Create Account');
    document.getElementById('authSubmit').textContent = mode === 'login' ? 'Hyr' : 'Krijo Llogari';
    document.getElementById('authNameGroup').style.display = mode === 'login' ? 'none' : 'block';
    document.getElementById('authMode').value = mode;
}

function hideAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

function handleAuth() {
    var mode = document.getElementById('authMode').value;
    var email = document.getElementById('authEmail').value.trim();
    var password = document.getElementById('authPassword').value.trim();
    var name = document.getElementById('authName').value.trim();

    if (!email || !password) { alert('Plotëso të gjitha fushat!'); return; }
    if (mode === 'register' && !name) { alert('Shkruaj emrin!'); return; }

    var body = { email: email, password: password };
    if (mode === 'register') body.name = name;

    api(mode === 'login' ? '/login' : '/register', {
        method: 'POST',
        body: body
    }).then(function(data) {
        if (data.error) { alert(data.error); return; }
        currentUser = data.user;
        userToken = data.token;
        localStorage.setItem('vita_user', JSON.stringify(currentUser));
        localStorage.setItem('vita_token', userToken);
        hideAuthModal();
        updateAuthUI();
        loadCart();
    });
}

function logout() {
    currentUser = null;
    userToken = '';
    localStorage.removeItem('vita_user');
    localStorage.removeItem('vita_token');
    updateAuthUI();
    document.getElementById('cartCount').textContent = '0';
    document.getElementById('cartCount').style.display = 'none';
}

function updateAuthUI() {
    var loginBtn = document.getElementById('navLoginBtn');
    var userBtn = document.getElementById('navUserBtn');
    var userName = document.getElementById('navUserName');
    var coinsDisplay = document.getElementById('navCoins');

    if (currentUser) {
        loginBtn.style.display = 'none';
        userBtn.style.display = 'flex';
        userName.textContent = currentUser.name;
        coinsDisplay.textContent = currentUser.coins || 0;
        coinsDisplay.style.display = 'inline';
    } else {
        loginBtn.style.display = 'inline-block';
        userBtn.style.display = 'none';
        coinsDisplay.style.display = 'none';
    }
}

// ==================== CART ====================

function loadCart() {
    if (!userToken) return;
    api('/cart').then(function(data) {
        if (data.error) return;
        var count = data.count || 0;
        var el = document.getElementById('cartCount');
        el.textContent = count;
        el.style.display = count > 0 ? 'flex' : 'none';
    });
}

function addToCart(productId, quantity) {
    if (!userToken) { showAuthModal('login'); return; }
    quantity = quantity || 1;
    api('/cart/add', {
        method: 'POST',
        body: { product_id: productId, quantity: quantity }
    }).then(function(data) {
        if (data.error) { alert(data.error); return; }
        loadCart();
        // Flash feedback
        var cartIcon = document.getElementById('cartIcon');
        cartIcon.style.transform = 'scale(1.3)';
        setTimeout(function() { cartIcon.style.transform = 'scale(1)'; }, 200);
    });
}

function showCartModal() {
    if (!userToken) { showAuthModal('login'); return; }
    api('/cart').then(function(data) {
        if (data.error) return;
        var html = '<h3 style="margin-bottom:1rem;">Shporta</h3>';
        if (data.items.length === 0) {
            html += '<p>Shporta është bosh.</p>';
        } else {
            data.items.forEach(function(item) {
                html += '<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">' +
                    '<img src="' + item.image + '" style="width:40px;height:40px;border-radius:8px;object-fit:contain;">' +
                    '<div style="flex:1;"><strong>' + item.name_sq + '</strong><br>' +
                    '<small>' + item.quantity + 'x €' + item.price.toFixed(2) + '</small></div>' +
                    '<span style="font-weight:700;">€' + item.subtotal.toFixed(2) + '</span>' +
                    '<button onclick="removeFromCart(' + item.id + ')" style="background:none;border:none;color:#e74c3c;cursor:pointer;font-size:1.2rem;">×</button>' +
                    '</div>';
            });
            html += '<div style="margin-top:1rem;display:flex;justify-content:space-between;align-items:center;">' +
                '<strong>Total: €' + data.total.toFixed(2) + '</strong>' +
                '<button onclick="placeOrder()" style="background:var(--accent);color:white;border:none;padding:10px 24px;border-radius:8px;cursor:pointer;font-weight:600;">Porosit</button>' +
                '</div>';
        }
        html += '<button onclick="hideCartModal()" style="margin-top:12px;background:none;border:1px solid var(--border);padding:8px 20px;border-radius:8px;cursor:pointer;">Mbyll</button>';
        document.getElementById('cartModalContent').innerHTML = html;
        document.getElementById('cartModal').style.display = 'flex';
    });
}

function hideCartModal() {
    document.getElementById('cartModal').style.display = 'none';
}

function removeFromCart(productId) {
    api('/cart/remove/' + productId, { method: 'DELETE' }).then(function() {
        loadCart();
        showCartModal(); // refresh
    });
}

function placeOrder() {
    api('/orders/place', { method: 'POST' }).then(function(data) {
        if (data.error) { alert(data.error); return; }
        alert('Porosi e suksesshme! Total: €' + data.total.toFixed(2) + ' (-€' + data.discount.toFixed(2) + ')\nCoins: +' + data.coins_earned + ' 🪙');
        hideCartModal();
        loadCart();
        // Refresh user coins
        if (currentUser) {
            currentUser.coins = (currentUser.coins || 0) + data.coins_earned;
            localStorage.setItem('vita_user', JSON.stringify(currentUser));
            updateAuthUI();
        }
    });
}

// ==================== RUSH HOUR BANNER ====================

function loadRushHourBanner() {
    api('/rush-hours').then(function(data) {
        var banner = document.getElementById('rushBanner');
        if (!data.active) {
            banner.style.display = 'none';
            return;
        }

        // Update countdown
        var seconds = data.seconds_left;
        var updateCountdown = function() {
            if (seconds <= 0) {
                banner.style.display = 'none';
                return;
            }
            var m = Math.floor(seconds / 60);
            var s = seconds % 60;
            document.getElementById('rushTimer').textContent = m + ':' + (s < 10 ? '0' : '') + s;
            seconds--;
        };
        updateCountdown();
        setInterval(updateCountdown, 1000);

        document.getElementById('rushName').textContent = data.active.name_sq;
        document.getElementById('rushDiscount').textContent = '-' + data.active.discount + '%';
        banner.style.display = 'block';

        // Mark discounted products
        var discountedIds = data.products.map(function(p) { return p.id; });
        document.querySelectorAll('.product-card').forEach(function(card) {
            var pid = parseInt(card.getAttribute('data-pid'));
            if (discountedIds.indexOf(pid) >= 0) {
                var badge = card.querySelector('.rush-badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'rush-badge';
                    badge.textContent = '-' + data.active.discount + '%';
                    card.appendChild(badge);
                }
            }
        });
    });
}

// ==================== PRODUCT PRICES ====================

function loadProductPrices() {
    api('/products').then(function(data) {
        var rush = data.rush_hour;
        var products = data.products;

        // Show rush banner if active
        if (rush) {
            document.getElementById('rushBanner').style.display = 'block';
            document.getElementById('rushName').textContent = rush.name_sq + ' Vrapo! ⚡';
            document.getElementById('rushDiscount').textContent = '-' + rush.discount + '%';
            loadRushHourBanner();
        }

        // Update product cards with prices
        products.forEach(function(p) {
            var card = document.querySelector('.product-card[data-slug="' + p.slug + '"]');
            if (!card) return;
            card.setAttribute('data-pid', p.id);

            var priceEl = card.querySelector('.product-price');
            if (!priceEl) {
                priceEl = document.createElement('div');
                priceEl.className = 'product-price';
                card.appendChild(priceEl);
            }

            if (p.discount_percent > 0) {
                priceEl.innerHTML = '<span class="old-price">€' + p.price.toFixed(2) + '</span> ' +
                    '<span class="sale-price">€' + p.sale_price.toFixed(2) + '</span> ' +
                    '<span class="discount-tag">-' + p.discount_percent + '%</span>';
            } else {
                priceEl.innerHTML = '<span class="current-price">€' + p.price.toFixed(2) + '</span>';
            }

            // Add to cart button
            var btn = card.querySelector('.add-cart-btn');
            if (!btn) {
                btn = document.createElement('button');
                btn.className = 'add-cart-btn';
                btn.setAttribute('data-sq', 'Shto në Shportë');
                btn.setAttribute('data-en', 'Add to Cart');
                btn.textContent = 'Shto në Shportë';
                btn.onclick = function(e) {
                    e.stopPropagation();
                    addToCart(p.id, 1);
                };
                card.appendChild(btn);
            }
        });
    });
}

// ==================== GAME REWARDS ====================

function submitGameReward(product, testsRun, testsOk, testsBad, decision, wasCorrect) {
    if (!userToken) return;
    api('/game/result', {
        method: 'POST',
        body: {
            product: product,
            tests_run: testsRun,
            tests_ok: testsOk,
            tests_bad: testsBad,
            decision: decision,
            was_correct: wasCorrect
        }
    }).then(function(data) {
        if (data.coins_earned > 0) {
            // Show floating coins animation
            showCoinsEarned(data.coins_earned);
        }
        if (currentUser) {
            currentUser.coins = data.total_coins;
            localStorage.setItem('vita_user', JSON.stringify(currentUser));
            updateAuthUI();
        }
    });
}

function showCoinsEarned(amount) {
    var el = document.createElement('div');
    el.className = 'coins-earned';
    el.textContent = '+🪙 ' + amount;
    document.getElementById('gameLab').appendChild(el);
    setTimeout(function() { el.remove(); }, 2000);
}

// ==================== INIT ====================

function initAPI() {
    updateAuthUI();
    loadCart();
    if (document.getElementById('products').classList.contains('active')) {
        loadProductPrices();
    }
}

// Hook into navigateTo to load products when that page opens
var originalNavigateTo = navigateTo;
navigateTo = function(page) {
    originalNavigateTo(page);
    if (page === 'products') {
        setTimeout(loadProductPrices, 300);
    }
};

document.addEventListener('DOMContentLoaded', function() {
    initAPI();
    loadRushHourBanner();
    setInterval(loadRushHourBanner, 60000); // Refresh every minute
});
