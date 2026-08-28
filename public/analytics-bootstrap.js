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
    var gaScript = document.createElement('script');
    gaScript.async = true;
    gaScript.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(containerId);
    document.head.appendChild(gaScript);

    window.gtag('js', new Date());
    window.gtag('config', containerId);

    var originalPush = window.dataLayer.push;
    window.dataLayer.push = function () {
      for (var i = 0; i < arguments.length; i++) {
        var item = arguments[i];
        if (item && typeof item === 'object' && typeof item.event === 'string' && item.event !== 'gtm.js') {
          var eventName = item.event;
          var params = Object.assign({}, item);
          delete params.event;
          window.gtag('event', eventName, params);
        }
      }
      return originalPush.apply(window.dataLayer, arguments);
    };
  }
})();
