-- Migration: Add CollateralRequest table
-- Created: 2025-11-07

CREATE TABLE IF NOT EXISTS collateral_requests (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    collateral_item_id INTEGER NOT NULL,
    requester_username VARCHAR(100) NOT NULL,
    event_details TEXT NOT NULL,
    needed_by_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    approved_by VARCHAR(100),
    decline_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_collateral_item_id (collateral_item_id),
    INDEX idx_requester_username (requester_username),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    
    FOREIGN KEY (collateral_item_id) REFERENCES collateral_items(id) ON DELETE CASCADE
);

-- Add comment to the table
ALTER TABLE collateral_requests COMMENT = 'Stores user requests for collateral items with approval workflow';
