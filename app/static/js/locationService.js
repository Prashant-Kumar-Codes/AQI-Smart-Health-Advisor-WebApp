/*
 * Centralized Location Service
 * Handles all location-based operations with precise geocoding and AQI fetching
 */

// Only create if not already defined (prevents duplicate errors)
if (typeof window.LocationService === 'undefined') {
    
    window.LocationService = {
        // Configuration
        NOMINATIM_BASE: 'https://nominatim.openstreetmap.org',
        AQI_API_BASE: '/api/aqi',
        
        /*
         * Get precise coordinates from location name (using backend)
         * @param {string} locationName - City name or address
         * @returns {Promise<Object>} - {lat, lng, displayName, address}
         */
        async getCoordinatesFromName(locationName) {
            if (!locationName || locationName.trim().length < 2) {
                throw new Error('Please enter a valid location name');
            }

            try {
                console.log(`🔍 Getting coordinates via backend for: ${locationName}`);
                
                // Use backend API which handles geocoding server-side
                const response = await fetch(
                    `/api/aqi/city/${encodeURIComponent(locationName)}`,
                    {
                        method: 'GET',
                        credentials: 'include'
                    }
                );

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `Location "${locationName}" not found`);
                }

                const data = await response.json();
                
                // Extract coordinates from backend response
                const lat = data.city?.geo?.[0] || null;
                const lng = data.city?.geo?.[1] || null;
                const cityName = data.city?.name || locationName;

                if (!lat || !lng) {
                    throw new Error('Could not determine coordinates for this location');
                }

                console.log(`✅ Coordinates retrieved: ${cityName} (${lat.toFixed(4)}, ${lng.toFixed(4)})`);

                return {
                    lat: lat,
                    lng: lng,
                    displayName: cityName,
                    fullAddress: data.precise_location || cityName,
                    address: {}
                };
            } catch (error) {
                console.error('❌ Geocoding error:', error);
                throw error;
            }
        },

        /*
         * Get precise location name from coordinates (using backend)
         * @param {number} lat - Latitude
         * @param {number} lng - Longitude
         * @returns {Promise<Object>} - {displayName, fullAddress, address}
         */
        async getNameFromCoordinates(lat, lng) {
            if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
                throw new Error('Invalid coordinates');
            }

            try {
                console.log(`📍 Getting location name via backend: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
                
                // Use backend API which gets location name from AQI data
                const response = await fetch(
                    `/api/aqi/geo?lat=${lat}&lng=${lng}`,
                    {
                        method: 'GET',
                        credentials: 'include'
                    }
                );

                if (!response.ok) {
                    throw new Error('Could not get location name');
                }

                const data = await response.json();
                
                const cityName = data.city?.name || data.precise_location || 'Unknown Location';

                console.log(`✅ Location name retrieved: ${cityName}`);

                return {
                    displayName: cityName,
                    fullAddress: data.precise_location || cityName,
                    address: {}
                };
            } catch (error) {
                console.error('❌ Reverse geocoding error:', error);
                // Return a fallback instead of throwing
                return {
                    displayName: 'Selected Location',
                    fullAddress: `${lat.toFixed(4)}, ${lng.toFixed(4)}`,
                    address: {}
                };
            }
        },

        /*
         * Get current device location with high accuracy
         * @returns {Promise<Object>} - {lat, lng, accuracy, displayName}
         */
        async getCurrentLocation() {
            if (!navigator.geolocation) {
                throw new Error('Geolocation is not supported by your browser');
            }

            return new Promise((resolve, reject) => {
                const options = {
                    enableHighAccuracy: true,
                    timeout: 20000,
                    maximumAge: 0
                };

                console.log('📡 Getting current location...');

                navigator.geolocation.getCurrentPosition(
                    async (position) => {
                        try {
                            const lat = position.coords.latitude;
                            const lng = position.coords.longitude;
                            const accuracy = position.coords.accuracy;

                            console.log(`✅ Location acquired: ${lat.toFixed(6)}, ${lng.toFixed(6)} (±${accuracy.toFixed(0)}m)`);

                            // Get location name from backend
                            const locationInfo = await this.getNameFromCoordinates(lat, lng);

                            resolve({
                                lat: lat,
                                lng: lng,
                                accuracy: accuracy,
                                displayName: locationInfo.displayName,
                                fullAddress: locationInfo.fullAddress,
                                address: locationInfo.address
                            });
                        } catch (error) {
                            // Even if we can't get the name, return coordinates
                            resolve({
                                lat: position.coords.latitude,
                                lng: position.coords.longitude,
                                accuracy: position.coords.accuracy,
                                displayName: 'Current Location',
                                fullAddress: `${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`,
                                address: {}
                            });
                        }
                    },
                    (error) => {
                        let errorMessage = 'Unable to retrieve your location. ';
                        
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMessage += 'Please allow location access in your browser settings.';
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMessage += 'Location information is unavailable.';
                                break;
                            case error.TIMEOUT:
                                errorMessage += 'Location request timed out. Please try again.';
                                break;
                            default:
                                errorMessage += 'An unknown error occurred.';
                        }
                        
                        console.error('❌ Geolocation error:', errorMessage);
                        reject(new Error(errorMessage));
                    },
                    options
                );
            });
        },

        /*
         * Fetch AQI data for coordinates
         * @param {number} lat - Latitude
         * @param {number} lng - Longitude
         * @returns {Promise<Object>} - AQI data
         */
        async getAQIByCoordinates(lat, lng) {
            try {
                console.log(`🌡️ Fetching AQI for coordinates: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
                
                const response = await fetch(
                    `${this.AQI_API_BASE}/geo?lat=${lat}&lng=${lng}`,
                    {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json'
                        },
                        credentials: 'include'
                    }
                );

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Failed to fetch AQI data');
                }

                const data = await response.json();
                console.log(`✅ AQI data received: ${data.aqi}`);
                
                return data;
            } catch (error) {
                console.error('❌ AQI fetch error:', error);
                throw error;
            }
        },

        /*
         * Fetch AQI data for location name
         * @param {string} cityName - City name
         * @returns {Promise<Object>} - AQI data
         */
        async getAQIByCity(cityName) {
            try {
                console.log(`🌡️ Fetching AQI for city: ${cityName}`);
                
                const response = await fetch(
                    `${this.AQI_API_BASE}/city/${encodeURIComponent(cityName)}`,
                    {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json'
                        },
                        credentials: 'include'
                    }
                );

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Failed to fetch AQI data');
                }

                const data = await response.json();
                console.log(`✅ AQI data received: ${data.aqi}`);
                
                return data;
            } catch (error) {
                console.error('❌ AQI fetch error:', error);
                throw error;
            }
        },

        /*
         * Complete flow: Location name -> Coordinates -> AQI
         * @param {string} locationName - City name or address
         * @returns {Promise<Object>} - {location, aqiData}
         */
        async getAQIFromLocationName(locationName) {
            try {
                // Step 1: Get coordinates and AQI data (backend does both)
                const location = await this.getCoordinatesFromName(locationName);
                
                // Step 2: Get AQI data using coordinates
                const aqiData = await this.getAQIByCoordinates(location.lat, location.lng);
                
                return {
                    location: location,
                    aqiData: aqiData
                };
            } catch (error) {
                throw error;
            }
        },

        /*
         * Complete flow: Current location -> Coordinates -> AQI
         * @returns {Promise<Object>} - {location, aqiData}
         */
        async getAQIFromCurrentLocation() {
            try {
                // Step 1: Get current location
                const location = await this.getCurrentLocation();
                
                // Step 2: Get AQI data
                const aqiData = await this.getAQIByCoordinates(location.lat, location.lng);
                
                return {
                    location: location,
                    aqiData: aqiData
                };
            } catch (error) {
                throw error;
            }
        },

        /*Uncaught SyntaxError: Identifier 'currentAQIData' has already been dec
         * Search locations with autocomplete (disabled - would need backend implementation)
         * @param {string} query - Search query
         * @param {number} limit - Max results
         * @returns {Promise<Array>} - List of locations
         */
        async searchLocations(query, limit = 5) {
            // Autocomplete feature requires backend implementation to avoid CORS issues
            console.log('⚠️ Autocomplete search disabled - use backend implementation if needed');
            return [];
        },

        /*
         * Detect city from IP address
         * @returns {Promise<string|null>} - City name or null
         */
        async detectCity() {
            try {
                const res = await fetch('/api/location', {
                    credentials: 'include'
                });
                const data = await res.json();
                return data.city || null;
            } catch (error) {
                console.error('❌ City detection error:', error);
                return null;
            }
        }
    };
    
    console.log('✅ LocationService loaded');
} else {
    console.log('ℹ️ LocationService already exists');
}