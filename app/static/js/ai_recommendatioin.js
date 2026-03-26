/**
 * Personalized Gemini AI Health Recommendations
 * NO MAP FEATURES - Only AI recommendations based on user profile
 */

// ============================================================================
// PERSONALIZED AI RECOMMENDATIONS
// ============================================================================

async function fetchPersonalizedRecommendation(aqiData) {
    console.log('🤖 Fetching personalized AI recommendation...');
    
    const recommendationContent = document.getElementById('personalizedRecommendation');
    const subtitle = document.getElementById('recommendationSubtitle');
    
    if (!recommendationContent) {
        console.warn('⚠️ Recommendation element not found in DOM');
        return;
    }
    
    // Show loading state
    recommendationContent.innerHTML = `
        <div class="loading-recommendation">
            <span>Generating personalized health recommendations</span>
            <div class="loading-dots">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch('/api/aqi/personalized-recommendation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                aqi: aqiData.aqi,
                category: aqiData.category,
                location: aqiData.city?.name || aqiData.precise_location || 'Unknown Location',
                pollutants: {
                    pm25: aqiData.pollutants?.pm25,
                    pm10: aqiData.pollutants?.pm10,
                    o3: aqiData.pollutants?.o3,
                    no2: aqiData.pollutants?.no2,
                    so2: aqiData.pollutants?.so2,
                    co: aqiData.pollutants?.co
                },
                weather: aqiData.weather || aqiData.enhanced_weather,
                dominant_pollutant: aqiData.dominentpol
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch recommendation');
        }
        
        const data = await response.json();
        
        console.log('✅ AI recommendation received:', {
            personalized: data.personalized,
            has_health_profile: data.has_health_profile,
            source: data.source,
            length: data.recommendation?.length
        });
        
        // Update subtitle based on personalization level
        if (subtitle) {
            if (data.has_health_profile) {
                subtitle.textContent = '✨ Fully Personalized (Health Profile + User Data)';
                subtitle.style.color = '#7c3aed';
            } else if (data.personalized) {
                subtitle.textContent = '✨ Personalized Based on Your Profile';
                subtitle.style.color = '#7c3aed';
            } else {
                subtitle.textContent = 'Powered by Google Gemini AI';
                subtitle.style.color = '#0369a1';
            }
        }
        
        // Display recommendation with formatting
        recommendationContent.innerHTML = formatRecommendation(data.recommendation);
        
        console.log('✅ AI recommendation displayed successfully');
        
    } catch (error) {
        console.error('❌ Error fetching personalized recommendation:', error);
        
        // Show fallback
        if (subtitle) {
            subtitle.textContent = 'General Recommendations';
            subtitle.style.color = '#64748b';
        }
        
        recommendationContent.innerHTML = getFallbackRecommendation(aqiData.aqi, aqiData.category);
    }
}

function formatRecommendation(text) {
    if (!text) {
        return 'No recommendation available.';
    }
    
    let formatted = text;
    
    // Convert markdown-style bold to HTML
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert bullet points to HTML bullets
    formatted = formatted.replace(/^- /gm, '• ');
    formatted = formatted.replace(/^\* /gm, '• ');
    
    // Add line breaks for better readability
    formatted = formatted.replace(/\n/g, '<br>');
    
    // Make emojis slightly larger
    formatted = formatted.replace(/💡|🚨|⚠️|✅|❌|🏥|🌱|😷|🌍|🫁|🚬|⚕️|📍/g, 
        '<span style="font-size: 1.2em;">$&</span>');
    
    return formatted;
}

function getFallbackRecommendation(aqi, category) {
    const fallbacks = {
        'Good': `
            <strong>✅ Excellent Air Quality!</strong><br><br>
            The current air quality is perfect for all outdoor activities. You can:<br>
            • Enjoy extended outdoor exercise without concern<br>
            • Open windows for natural ventilation<br>
            • Plan outdoor events and sports<br>
            • No special precautions needed<br><br>
            <em>This is ideal air quality. Make the most of this clean air day!</em>
        `,
        'Moderate': `
            <strong>🟡 Acceptable Air Quality</strong><br><br>
            Air quality is generally acceptable for most people:<br>
            • Normal outdoor activities are safe<br>
            • Sensitive individuals may want to limit prolonged exertion<br>
            • Consider indoor exercise if unusually sensitive<br>
            • Monitor for any symptoms<br><br>
            <em>Generally safe conditions. Sensitive groups should stay aware.</em>
        `,
        'Unhealthy for Sensitive Groups': `
            <strong>🟠 Caution for Sensitive Groups</strong><br><br>
            Sensitive individuals should take precautions:<br>
            • Limit outdoor activities if you have respiratory conditions<br>
            • Wear N95/KN95 masks when spending time outside<br>
            • Keep windows closed during peak pollution hours<br>
            • Use air purifiers indoors if available<br>
            • Keep rescue medications handy<br><br>
            <em>Seek medical care if symptoms like coughing or breathing difficulties persist.</em>
        `,
        'Unhealthy': `
            <strong>🔴 Unhealthy Air Quality</strong><br><br>
            Everyone should reduce outdoor exposure:<br>
            • Minimize time spent outdoors<br>
            • Wear high-quality masks (N95/KN95) when outside<br>
            • Keep all windows and doors closed<br>
            • Run air purifiers continuously<br>
            • Postpone strenuous outdoor activities<br>
            • Stay well-hydrated and monitor symptoms<br><br>
            <em>Seek medical attention if experiencing chest pain, headaches, or respiratory distress.</em>
        `,
        'Very Unhealthy': `
            <strong>🟣 Very Unhealthy Air Quality</strong><br><br>
            Serious health effects for everyone:<br>
            • Avoid all outdoor activities<br>
            • Stay indoors with air purification<br>
            • Wear N95 masks for any outdoor exposure<br>
            • Seal windows and doors<br>
            • Keep emergency medications accessible<br>
            • Seek medical attention if experiencing symptoms<br><br>
            <em>⚠️ THIS IS A HEALTH EMERGENCY. Call emergency services if needed.</em>
        `,
        'Hazardous': `
            <strong>⚫ Hazardous Air Quality - EMERGENCY!</strong><br><br>
            Everyone is at serious health risk:<br>
            • <strong>Stay indoors at all times</strong><br>
            • Run air purifiers continuously<br>
            • Seal all windows and doors<br>
            • Wear N95 masks even indoors if needed<br>
            • Seek immediate medical help for any symptoms<br>
            • Follow emergency guidelines and evacuation orders<br><br>
            <em>🚨 PUBLIC HEALTH CRISIS: This is a life-threatening situation. Call emergency services immediately if experiencing symptoms.</em>
        `
    };
    
    return fallbacks[category] || '<em>Unable to generate recommendation at this time.</em>';
}

// ============================================================================
// PREDICTION ENHANCEMENTS
// ============================================================================

function enhancePredictionDisplay(predictionData) {
    console.log('📊 Enhancing prediction display...');
    
    const graphContainer = document.getElementById('predictionGraphContainer');
    
    if (graphContainer) {
        // Add fade-in animation
        graphContainer.style.opacity = '0';
        graphContainer.style.display = 'block';
        
        setTimeout(() => {
            graphContainer.style.transition = 'opacity 0.5s ease';
            graphContainer.style.opacity = '1';
        }, 100);
    }
    
    // Enhance insights with icons and color-coded text
    const insights = document.getElementById('predictionInsights');
    if (insights && predictionData.insights) {
        let enhancedInsights = predictionData.insights;
        
        // Add visual emphasis with icons and colors
        enhancedInsights = enhancedInsights.replace(/Peak AQI/g, '🎯 <strong>Peak AQI</strong>');
        enhancedInsights = enhancedInsights.replace(/improving/gi, '📈 <span style="color: #059669; font-weight: 600;">improving</span>');
        enhancedInsights = enhancedInsights.replace(/worsening/gi, '📉 <span style="color: #dc2626; font-weight: 600;">worsening</span>');
        enhancedInsights = enhancedInsights.replace(/stable/gi, '➡️ <span style="color: #0891b2; font-weight: 600;">stable</span>');
        enhancedInsights = enhancedInsights.replace(/deteriorating/gi, '⚠️ <span style="color: #ea580c; font-weight: 600;">deteriorating</span>');
        
        insights.innerHTML = enhancedInsights;
        console.log('✅ Insights enhanced');
    }
}

// ============================================================================
// INTEGRATION WITH EXISTING CODE
// ============================================================================

// Hook into existing fetchAIRecommendation function if it exists
if (typeof window.fetchAIRecommendation !== 'undefined') {
    const originalFetchAIRecommendation = window.fetchAIRecommendation;
    
    window.fetchAIRecommendation = async function(aqi) {
        console.log('🔄 Calling original fetchAIRecommendation...');
        
        // Call original function first
        try {
            await originalFetchAIRecommendation(aqi);
        } catch (error) {
            console.warn('⚠️ Original fetchAIRecommendation failed:', error);
        }
        
        // Then fetch personalized Gemini recommendation
        if (window.currentAQIData) {
            await fetchPersonalizedRecommendation(window.currentAQIData);
        } else {
            console.warn('⚠️ No currentAQIData available for personalized recommendation');
        }
    };
    
    console.log('✅ fetchAIRecommendation hooked successfully');
} else {
    // Define the function if it doesn't exist
    window.fetchAIRecommendation = async function(aqi) {
        console.log('📝 fetchAIRecommendation called (new definition)');
        
        if (window.currentAQIData) {
            await fetchPersonalizedRecommendation(window.currentAQIData);
        } else {
            console.warn('⚠️ No currentAQIData available');
        }
    };
    
    console.log('✅ fetchAIRecommendation created');
}

// Hook into existing displayPredictions function if it exists
if (typeof window.displayPredictions !== 'undefined') {
    const originalDisplayPredictions = window.displayPredictions;
    
    window.displayPredictions = function(predictionData) {
        console.log('🔄 Calling original displayPredictions...');
        
        // Call original function
        originalDisplayPredictions(predictionData);
        
        // Enhance the display
        enhancePredictionDisplay(predictionData);
    };
    
    console.log('✅ displayPredictions hooked successfully');
} else {
    console.log('ℹ️ displayPredictions not found (may not be implemented yet)');
}

// ============================================================================
// INITIALIZATION
// ============================================================================

console.log('✅ Personalized AI recommendations loaded (Gemini API)');
console.log('   Features: AI health advice based on user profile + health data');
console.log('   NO map features included');