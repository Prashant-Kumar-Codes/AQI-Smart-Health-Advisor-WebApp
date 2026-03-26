// ========== Wrap in IIFE to prevent duplicate declarations ==========
(function() {
    'use strict';
    
    // ========== Global State (scoped to IIFE) ==========
    let trackingActive = false;
    let watchId = null;
    let currentPosition = null;
    let lastAlertPosition = null;
    let lastAlertAQI = null;
    let currentAQIData = null;
    let alertCount = 0;
    let checkInterval = null;
    let lastEmailSentTime = null;

    // Configuration
    const DISTANCE_THRESHOLD_KM = 10;
    const AQI_CHANGE_THRESHOLD = 50;
    const CHECK_INTERVAL_MS = 60000; // Check every 60 seconds
    const MIN_EMAIL_INTERVAL_MS = 1800000; // 30 minutes between emails

    // ========== Utility Functions ==========
    function calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth's radius in km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    function getAQICategory(aqi) {
        if (aqi <= 50) return { category: 'Good', class: 'alert-success' };
        if (aqi <= 100) return { category: 'Moderate', class: 'alert-success' };
        if (aqi <= 150) return { category: 'Unhealthy for Sensitive Groups', class: 'alert-warning' };
        if (aqi <= 200) return { category: 'Unhealthy', class: 'alert-warning' };
        if (aqi <= 300) return { category: 'Very Unhealthy', class: 'alert-danger' };
        return { category: 'Hazardous', class: 'alert-danger' };
    }

    function formatTimestamp(date) {
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        return date.toLocaleString('en-US', options);
    }

    function canSendEmail() {
        if (!lastEmailSentTime) return true;
        
        const timeSinceLastEmail = Date.now() - lastEmailSentTime;
        return timeSinceLastEmail >= MIN_EMAIL_INTERVAL_MS;
    }

    // ========== Location Tracking Functions ==========
    async function startTracking() {
        console.log('=== Starting location tracking ===');
        
        // Check if user is logged in
        try {
            const response = await fetch('/api/user/check');
            if (!response.ok) {
                alert('You must be logged in to use Live Tracking.\n\nClick OK to go to login page.');
                window.location.href = '/login_signup?redirect=live_track';
                return;
            }
        } catch (error) {
            console.error('Error checking login status:', error);
            alert('Failed to verify login status. Please try again.');
            return;
        }
        
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }
        
        trackingActive = true;
        updateTrackingUI();
        
        // Get initial position with high accuracy
        const options = {
            enableHighAccuracy: true,
            timeout: 20000,
            maximumAge: 0
        };
        
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                currentPosition = position;
                await handlePositionUpdate(position);
                
                // Start continuous watching with high accuracy
                watchId = navigator.geolocation.watchPosition(
                    handlePositionUpdate,
                    handlePositionError,
                    {
                        enableHighAccuracy: true,
                        timeout: 20000,
                        maximumAge: 0
                    }
                );
                
                // Start periodic AQI checks
                checkInterval = setInterval(checkAQIChange, CHECK_INTERVAL_MS);
                
                console.log('Tracking started successfully with high accuracy GPS');
            },
            (error) => {
                handlePositionError(error);
                stopTracking();
            },
            options
        );
    }

    function stopTracking() {
        console.log('=== Stopping location tracking ===');
        
        trackingActive = false;
        
        if (watchId !== null) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
        }
        
        if (checkInterval !== null) {
            clearInterval(checkInterval);
            checkInterval = null;
        }
        
        updateTrackingUI();
        console.log('Tracking stopped');
    }

    async function handlePositionUpdate(position) {
        const { latitude, longitude, accuracy } = position.coords;
        console.log(`Position updated: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} (±${accuracy.toFixed(0)}m)`);
        
        currentPosition = position;
        
        // Update UI with precise coordinates
        await updateLocationDisplay(latitude, longitude, accuracy);
        updateLastUpdateTime();
        
        // Fetch AQI for current location
        await fetchAndUpdateAQI(latitude, longitude);
        
        // Check if alert should be sent
        checkAndSendAlert(latitude, longitude);
    }

    function handlePositionError(error) {
        console.error('Position error:', error);
        
        let errorMessage = 'Unable to retrieve your location. ';
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMessage += 'Please allow location access in your browser settings.';
                break;
            case error.POSITION_UNAVAILABLE:
                errorMessage += 'Location information is unavailable.';
                break;
            case error.TIMEOUT:
                errorMessage += 'Location request timed out.';
                break;
            default:
                errorMessage += 'An unknown error occurred.';
        }
        
        alert(errorMessage);
    }

    // ✅ FIX: Use LocationService (backend) instead of direct Nominatim calls
    async function updateLocationDisplay(lat, lng, accuracy) {
        try {
            // Check if LocationService is available
            if (typeof LocationService === 'undefined') {
                throw new Error('LocationService not loaded');
            }
            
            console.log('🔍 Using LocationService for reverse geocoding');
            
            // ✅ Use centralized LocationService (goes through backend, no CORS issues)
            const locationInfo = await LocationService.getNameFromCoordinates(lat, lng);
            
            const locationName = locationInfo.displayName || 'Location detected';
            
            const locationNameEl = document.getElementById('locationName');
            const locationCoordsEl = document.getElementById('locationCoords');
            
            if (locationNameEl) {
                locationNameEl.textContent = locationName;
            }
            if (locationCoordsEl) {
                locationCoordsEl.textContent = 
                    `${lat.toFixed(6)}, ${lng.toFixed(6)} (±${accuracy.toFixed(0)}m)`;
            }
            
        } catch (error) {
            console.error('Geocoding error:', error);
            
            // Fallback to coordinates only
            const locationNameEl = document.getElementById('locationName');
            const locationCoordsEl = document.getElementById('locationCoords');
            
            if (locationNameEl) {
                locationNameEl.textContent = 'Location detected';
            }
            if (locationCoordsEl) {
                locationCoordsEl.textContent = 
                    `${lat.toFixed(6)}, ${lng.toFixed(6)} (±${accuracy.toFixed(0)}m)`;
            }
        }
    }

    function updateLastUpdateTime() {
        const now = new Date();
        const lastUpdateEl = document.getElementById('lastUpdate');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = formatTimestamp(now);
        }
    }

    // ========== AQI Functions ==========
    async function fetchAndUpdateAQI(lat, lng) {
        try {
            const response = await fetch(`/api/aqi/geo?lat=${lat}&lng=${lng}`);
            
            if (response.ok) {
                const data = await response.json();
                currentAQIData = data;
                
                console.log('AQI data fetched:', data);
                updateCurrentAQIDisplay(data);
                
                return data;
            } else {
                console.warn('Could not fetch AQI data');
                return null;
            }
        } catch (error) {
            console.error('Error fetching AQI data:', error);
            return null;
        }
    }

    function updateCurrentAQIDisplay(data) {
        const aqi = data.aqi || 0;
        const category = getAQICategory(aqi);
        
        // Update header badge
        const currentAQIEl = document.getElementById('currentAQI');
        if (currentAQIEl) {
            currentAQIEl.textContent = aqi;
        }
        
        // Show AQI card
        const aqiCard = document.getElementById('currentAQICard');
        if (aqiCard) {
            aqiCard.style.display = 'block';
        }
        
        // Update AQI values
        const aqiValueLargeEl = document.getElementById('aqiValueLarge');
        const aqiCategoryEl = document.getElementById('aqiCategory');
        
        if (aqiValueLargeEl) {
            aqiValueLargeEl.textContent = aqi;
        }
        if (aqiCategoryEl) {
            aqiCategoryEl.textContent = category.category;
        }
        
        // Update pollutant details
        const detailsDiv = document.getElementById('aqiDetails');
        if (!detailsDiv) return;
        
        let detailsHTML = '';
        
        if (data.iaqi) {
            if (data.iaqi.pm25?.v) {
                detailsHTML += `
                    <div class="pollutant-item">
                        <span class="pollutant-name">PM2.5</span>
                        <span class="pollutant-value">${data.iaqi.pm25.v.toFixed(1)} µg/m³</span>
                    </div>
                `;
            }
            if (data.iaqi.pm10?.v) {
                detailsHTML += `
                    <div class="pollutant-item">
                        <span class="pollutant-name">PM10</span>
                        <span class="pollutant-value">${data.iaqi.pm10.v.toFixed(1)} µg/m³</span>
                    </div>
                `;
            }
            if (data.iaqi.o3?.v) {
                detailsHTML += `
                    <div class="pollutant-item">
                        <span class="pollutant-name">Ozone (O₃)</span>
                        <span class="pollutant-value">${data.iaqi.o3.v.toFixed(1)} ppb</span>
                    </div>
                `;
            }
            if (data.iaqi.no2?.v) {
                detailsHTML += `
                    <div class="pollutant-item">
                        <span class="pollutant-name">NO₂</span>
                        <span class="pollutant-value">${data.iaqi.no2.v.toFixed(1)} ppb</span>
                    </div>
                `;
            }
        }
        
        detailsDiv.innerHTML = detailsHTML;
    }

    async function checkAQIChange() {
        if (!trackingActive || !currentPosition || !currentAQIData) return;
        
        console.log('Checking for AQI changes...');
        
        const { latitude, longitude } = currentPosition.coords;
        const newAQIData = await fetchAndUpdateAQI(latitude, longitude);
        
        if (!newAQIData) return;
        
        const newAQI = newAQIData.aqi || 0;
        
        // Check if AQI changed significantly
        if (lastAlertAQI !== null) {
            const aqiDiff = Math.abs(newAQI - lastAlertAQI);
            
            if (aqiDiff >= AQI_CHANGE_THRESHOLD) {
                console.log(`AQI changed by ${aqiDiff} (threshold: ${AQI_CHANGE_THRESHOLD})`);
                await sendAlert('aqi_change', latitude, longitude, newAQIData);
            }
        }
    }

    // ========== Alert Functions ==========
    async function checkAndSendAlert(lat, lng) {
        console.log('Checking if alert should be sent...');
        
        // Check if this is the first position
        if (lastAlertPosition === null) {
            console.log('First position - sending initial alert');
            await sendAlert('initial', lat, lng, currentAQIData);
            return;
        }
        
        // Calculate distance from last alert position
        const distance = calculateDistance(
            lastAlertPosition.lat,
            lastAlertPosition.lng,
            lat,
            lng
        );
        
        console.log(`Distance from last alert: ${distance.toFixed(2)} km (threshold: ${DISTANCE_THRESHOLD_KM} km)`);
        
        // Check if distance threshold exceeded
        if (distance >= DISTANCE_THRESHOLD_KM) {
            console.log('Distance threshold exceeded - sending alert');
            await sendAlert('location_change', lat, lng, currentAQIData);
        }
    }

    async function sendAlert(type, lat, lng, aqiData) {
        console.log(`Sending ${type} alert...`);
        
        // Check if we should send email
        const shouldSendEmail = canSendEmail() && (aqiData?.aqi > 50);
        
        if (!shouldSendEmail && aqiData?.aqi > 50) {
            console.log(`Skipping email - last email sent ${Math.round((Date.now() - lastEmailSentTime) / 60000)} minutes ago`);
        }
        
        try {
            const response = await fetch('/api/live-tracker/alert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({
                    type: type,
                    latitude: lat,
                    longitude: lng,
                    aqi: aqiData?.aqi || 0,
                    aqi_category: getAQICategory(aqiData?.aqi || 0).category,
                    pollutants: {
                        pm25: aqiData?.iaqi?.pm25?.v || null,
                        pm10: aqiData?.iaqi?.pm10?.v || null,
                        o3: aqiData?.iaqi?.o3?.v || null,
                        no2: aqiData?.iaqi?.no2?.v || null,
                        so2: aqiData?.iaqi?.so2?.v || null,
                        co: aqiData?.iaqi?.co?.v || null
                    },
                    city_name: aqiData?.city?.name || 'Unknown',
                    dominant_pollutant: aqiData?.dominentpol || null,
                    send_email: shouldSendEmail
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('Alert sent successfully:', data);
                
                // Update last alert position and AQI
                lastAlertPosition = { lat, lng };
                lastAlertAQI = aqiData?.aqi || 0;
                
                // Update email sent time if email was sent
                if (shouldSendEmail) {
                    lastEmailSentTime = Date.now();
                    console.log('Email sent time updated');
                }
                
                // Update alert count
                alertCount++;
                const alertCountEl = document.getElementById('alertCount');
                if (alertCountEl) {
                    alertCountEl.textContent = alertCount;
                }
                
                // Add alert to timeline
                addAlertToTimeline(data);
                
            } else {
                console.error('Failed to send alert:', response.status);
            }
            
        } catch (error) {
            console.error('Error sending alert:', error);
        }
    }

    // ========== UI Functions ==========
    function updateTrackingUI() {
        const startBtn = document.getElementById('startTrackingBtn');
        const stopBtn = document.getElementById('stopTrackingBtn');
        const trackingInfo = document.getElementById('trackingInfo');
        const trackingStatus = document.getElementById('trackingStatus');
        const controlPanel = document.querySelector('.tracking-control-panel');
        
        if (trackingActive) {
            if (startBtn) startBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-flex';
            if (trackingInfo) trackingInfo.style.display = 'block';
            if (trackingStatus) {
                trackingStatus.textContent = 'Active';
                trackingStatus.style.color = '#10b981';
            }
            
            // Add class to trigger animation
            if (controlPanel) {
                controlPanel.classList.add('tracking-active');
            }
        } else {
            if (startBtn) startBtn.style.display = 'inline-flex';
            if (stopBtn) stopBtn.style.display = 'none';
            if (trackingInfo) trackingInfo.style.display = 'none';
            if (trackingStatus) {
                trackingStatus.textContent = 'Inactive';
                trackingStatus.style.color = '#ef4444';
            }
            
            // Remove animation class
            if (controlPanel) {
                controlPanel.classList.remove('tracking-active');
            }
            
            // Reset location display
            const locationNameEl = document.getElementById('locationName');
            const locationCoordsEl = document.getElementById('locationCoords');
            
            if (locationNameEl) {
                locationNameEl.textContent = 'Not tracking';
            }
            if (locationCoordsEl) {
                locationCoordsEl.textContent = '';
            }
        }
    }

    function addAlertToTimeline(alertData) {
        const timeline = document.getElementById('alertTimeline');
        const noAlerts = document.getElementById('noAlerts');
        
        if (!timeline) return;
        
        // Hide "no alerts" message
        if (noAlerts) {
            noAlerts.style.display = 'none';
        }
        
        const alertItem = document.createElement('div');
        const category = getAQICategory(alertData.aqi);
        alertItem.className = `alert-item ${category.class}`;
        
        let alertHTML = `
            <div class="alert-header">
                <div class="alert-title">
                    ${alertData.type === 'initial' ? '📍 Initial Location' : 
                      alertData.type === 'location_change' ? '🚶 Location Changed' : 
                      '📊 AQI Changed'}
                </div>
                <div class="alert-timestamp">${formatTimestamp(new Date(alertData.timestamp))}</div>
            </div>
            <div class="alert-location">📍 ${alertData.location}</div>
            <div class="alert-aqi-info">
                <div class="aqi-badge">AQI: ${alertData.aqi}</div>
                <div class="aqi-badge">${category.category}</div>
            </div>
            <div class="alert-message">${alertData.message}</div>
        `;
        
        if (alertData.recommendations && alertData.recommendations.length > 0) {
            alertHTML += `
                <div class="alert-recommendations">
                    <div class="recommendations-title">🛡️ Important Actions:</div>
                    <ul class="recommendations-list">
            `;
            
            alertData.recommendations.forEach(rec => {
                alertHTML += `<li>${rec}</li>`;
            });
            
            alertHTML += `
                    </ul>
                </div>
            `;
        }
        
        alertItem.innerHTML = alertHTML;
        
        // Insert at the beginning of timeline
        timeline.insertBefore(alertItem, timeline.firstChild);
    }

    async function loadAlertHistory() {
        try {
            const response = await fetch('/api/live-tracker/alerts');
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.alerts && data.alerts.length > 0) {
                    const noAlerts = document.getElementById('noAlerts');
                    if (noAlerts) {
                        noAlerts.style.display = 'none';
                    }
                    
                    data.alerts.forEach(alert => {
                        addAlertToTimeline(alert);
                    });
                    
                    alertCount = data.alerts.length;
                    const alertCountEl = document.getElementById('alertCount');
                    if (alertCountEl) {
                        alertCountEl.textContent = alertCount;
                    }
                }
            }
        } catch (error) {
            console.error('Error loading alert history:', error);
        }
    }

    async function clearHistory() {
        if (!confirm('Are you sure you want to clear all alert history?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/live-tracker/alerts/clear', {
                method: 'POST',
                credentials: 'include'
            });
            
            if (response.ok) {
                // Clear timeline
                const timeline = document.getElementById('alertTimeline');
                if (timeline) {
                    timeline.innerHTML = `
                        <div class="no-alerts" id="noAlerts">
                            <div class="no-alerts-icon">🔭</div>
                            <p>No alerts yet. Start tracking to receive alerts!</p>
                        </div>
                    `;
                }
                
                // Reset alert count
                alertCount = 0;
                const alertCountEl = document.getElementById('alertCount');
                if (alertCountEl) {
                    alertCountEl.textContent = '0';
                }
                
                console.log('Alert history cleared');
            }
        } catch (error) {
            console.error('Error clearing history:', error);
            alert('Failed to clear history. Please try again.');
        }
    }

    // ========== Expose functions to global scope ==========
    window.startTracking = startTracking;
    window.stopTracking = stopTracking;
    window.clearHistory = clearHistory;

    // ========== Initialize ==========
    document.addEventListener('DOMContentLoaded', function() {
        console.log('=== Live Tracker page loaded ===');
        
        // Load alert history
        loadAlertHistory();
        
        // Initialize UI
        updateTrackingUI();
        
        console.log('=== Initialization complete ===');
    });

})(); // End IIFE