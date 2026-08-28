(function () {
  'use strict';

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () {
    window.dataLayer.push(arguments);
  };

  window.gtag('consent', 'default', {
    ad_storage: 'denied',
    analytics_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    wait_for_update: 500,
  });

  try {
    var storedConsent = window.localStorage.getItem('kesher_consent_v2');
    if (storedConsent === 'granted' || storedConsent === 'denied') {
      window.gtag('consent', 'update', {
        ad_storage: storedConsent,
        analytics_storage: storedConsent,
        ad_user_data: storedConsent,
        ad_personalization: storedConsent,
      });
    }
  } catch (_error) {
    // Local storage can be unavailable. The denied default remains authoritative.
  }

  var bootstrapScript = document.currentScript;
  var containerId = bootstrapScript && bootstrapScript.getAttribute('data-gtm-id');
  if (!containerId || containerId.indexOf('VITE_') === 0 || containerId === 'disabled') {
    return;
  }

  if (/^GTM-[A-Z0-9]+$/i.test(containerId)) {
    window.dataLayer.push({
      'gtm.start': new Date().getTime(),
      event: 'gtm.js',
    });

    var gtmScript = document.createElement('script');
    gtmScript.async = true;
    gtmScript.src = 'https://www.googletagmanager.com/gtm.js?id=' + encodeURIComponent(containerId);
    document.head.appendChild(gtmScript);
    return;
  }

  if (/^G-[A-Z0-9]+$/i.test(containerId)) {
    var nativePush = Array.prototype.push;
    var _googlePush = null;

    try {
      Object.defineProperty(window.dataLayer, 'push', {
        configurable: true,
        enumerable: false,
        get: function () {
          return function () {
            for (var i = 0; i < arguments.length; i++) {
              nativePush.call(window.dataLayer, arguments[i]);
            }
            if (_googlePush && typeof _googlePush === 'function') {
              return _googlePush.apply(window.dataLayer, arguments);
            }
          };
        },
        set: function (newPush) {
          _googlePush = newPush;
        },
      });
    } catch (_defErr) {
      // Safe fallback if property cannot be defined
    }

    window.gtag('js', new Date());
    window.gtag('config', containerId);

    var gaScript = document.createElement('script');
    gaScript.async = true;
    gaScript.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(containerId);
    document.head.appendChild(gaScript);
  }
})();
