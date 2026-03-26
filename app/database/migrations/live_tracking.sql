-- ============================================
-- SQL Table for Live Tracker Alerts
-- ============================================

USE aqi_app_db;

-- Create tracking_alerts table
CREATE TABLE IF NOT EXISTS tracking_alerts (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_email` VARCHAR(100) NOT NULL,
    `alert_type` VARCHAR(50) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `location` VARCHAR(200) NOT NULL,
    `latitude` DECIMAL(10, 8) NOT NULL,
    `longitude` DECIMAL(11, 8) NOT NULL,
    `aqi` INT NOT NULL,
    `aqi_category` VARCHAR(50) NOT NULL,
    `message` TEXT NOT NULL,
    `recommendations` JSON NOT NULL,
    `pollutants` JSON,
    `expiry_time` DATETIME NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to link with login_data table
    CONSTRAINT `fk_tracking_user_email` 
        FOREIGN KEY (`user_email`) 
        REFERENCES `login_data` (`email`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    
    -- Index for faster queries
    INDEX `idx_user_email` (`user_email`),
    INDEX `idx_expiry_time` (`expiry_time`),
    INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Automatic cleanup of expired alerts
-- ============================================

-- Create event to automatically delete expired alerts every hour
-- (This requires EVENT_SCHEDULER to be enabled)

DELIMITER $$

CREATE EVENT IF NOT EXISTS cleanup_expired_alerts
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    DELETE FROM tracking_alerts WHERE expiry_time < NOW();
END$$

DELIMITER ;

-- Enable the event scheduler (run this once)
SET GLOBAL event_scheduler = ON;

-- ============================================
-- Useful queries for monitoring
-- ============================================

-- View all active alerts for a user
-- SELECT * FROM tracking_alerts 
-- WHERE user_email = 'user@example.com' 
-- AND expiry_time >= NOW() 
-- ORDER BY timestamp DESC;

-- Count active alerts by user
-- SELECT user_email, COUNT(*) as alert_count 
-- FROM tracking_alerts 
-- WHERE expiry_time >= NOW() 
-- GROUP BY user_email;

-- View recent alerts (last 24 hours)
-- SELECT * FROM tracking_alerts 
-- WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR) 
-- ORDER BY timestamp DESC;