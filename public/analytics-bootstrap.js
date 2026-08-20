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
  if (!containerId || containerId.indexOf('VITE_') === 0 || !/^GTM-[A-Z0-9]+$/i.test(containerId)) {
    return;
  }

  window.dataLayer.push({
    'gtm.start': new Date().getTime(),
    event: 'gtm.js',
  });

  var script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtm.js?id=' + encodeURIComponent(containerId);
  document.head.appendChild(script);
})();
