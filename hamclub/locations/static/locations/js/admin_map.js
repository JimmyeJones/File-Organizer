/* Leaflet map picker injected into Django admin for models with latitude/longitude fields. */
(function () {
    'use strict';

    function initMapPicker() {
        var latField = document.getElementById('id_latitude');
        var lngField = document.getElementById('id_longitude');
        if (!latField || !lngField) return;

        /* --- Search box --- */
        var searchWrap = document.createElement('div');
        searchWrap.style.cssText = 'display:flex; gap:6px; margin:8px 0 4px;';

        var searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search address or place name, then press Enter…';
        searchInput.style.cssText = 'flex:1; padding:6px 10px; border:1px solid #ccc; border-radius:4px; font-size:13px;';

        var searchStatus = document.createElement('span');
        searchStatus.style.cssText = 'align-self:center; font-size:12px; color:#666; min-width:80px;';

        searchWrap.appendChild(searchInput);
        searchWrap.appendChild(searchStatus);

        /* --- Map container --- */
        var mapDiv = document.createElement('div');
        mapDiv.style.cssText = 'height:380px; border:1px solid #ccc; border-radius:4px; margin-bottom:8px;';

        var hint = document.createElement('p');
        hint.style.cssText = 'font-size:12px; color:#666; margin:0 0 8px;';
        hint.textContent = 'Click on the map to place a pin, drag to reposition, or search above. Leave blank to omit from map.';

        /* Insert elements after the longitude row */
        var lngRow = lngField.closest('.form-row') || lngField.parentNode;
        lngRow.insertAdjacentElement('afterend', hint);
        hint.insertAdjacentElement('afterend', mapDiv);
        mapDiv.insertAdjacentElement('beforebegin', searchWrap);

        /* --- Leaflet init --- */
        var hasCoords = latField.value !== '' && lngField.value !== '';
        var initLat = hasCoords ? parseFloat(latField.value) : 39.8283;
        var initLng = hasCoords ? parseFloat(lngField.value) : -98.5795;
        var initZoom = hasCoords ? 14 : 4;

        var map = L.map(mapDiv).setView([initLat, initLng], initZoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(map);

        var marker = null;

        function placeMarker(lat, lng, pan) {
            var latlng = L.latLng(lat, lng);
            if (marker) {
                marker.setLatLng(latlng);
            } else {
                marker = L.marker(latlng, { draggable: true }).addTo(map);
                marker.on('dragend', function (e) {
                    var pos = e.target.getLatLng();
                    setFields(pos.lat, pos.lng);
                });
            }
            setFields(lat, lng);
            if (pan) map.setView(latlng, Math.max(map.getZoom(), 14));
        }

        function setFields(lat, lng) {
            latField.value = lat.toFixed(6);
            lngField.value = lng.toFixed(6);
        }

        if (hasCoords) placeMarker(initLat, initLng, false);

        map.on('click', function (e) {
            placeMarker(e.latlng.lat, e.latlng.lng, false);
        });

        /* --- Address geocoding via Nominatim --- */
        searchInput.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            var query = searchInput.value.trim();
            if (!query) return;
            searchStatus.textContent = 'Searching…';
            fetch(
                'https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' +
                encodeURIComponent(query),
                { headers: { 'Accept-Language': 'en' } }
            )
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.length) {
                        searchStatus.textContent = 'Not found';
                        return;
                    }
                    searchStatus.textContent = '';
                    placeMarker(parseFloat(data[0].lat), parseFloat(data[0].lon), true);
                })
                .catch(function () { searchStatus.textContent = 'Error'; });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMapPicker);
    } else {
        initMapPicker();
    }
})();
