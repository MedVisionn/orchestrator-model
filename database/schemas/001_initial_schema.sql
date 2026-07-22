-- MedScanAI Database Schema
-- PostgreSQL 15+
-- HIPAA Compliant - Audit logging enabled

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create custom types
CREATE TYPE inference_status AS ENUM ('pending', 'processing', 'completed', 'failed');
CREATE TYPE model_status AS ENUM ('development', 'staging', 'production', 'deprecated');
CREATE TYPE feedback_status AS ENUM ('pending', 'reviewed', 'used_in_training');
CREATE TYPE severity_level AS ENUM ('mild', 'moderate', 'severe', 'critical');

-- =============================================================================
-- INFERENCE LOGS
-- =============================================================================
CREATE TABLE inference_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    
    -- DICOM Metadata (de-identified)
    study_instance_uid VARCHAR(128) NOT NULL,
    series_instance_uid VARCHAR(128),
    sop_instance_uid VARCHAR(128),
    patient_id_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for privacy
    
    -- Image metadata
    modality VARCHAR(10) NOT NULL DEFAULT 'CR',
    body_part VARCHAR(50) NOT NULL DEFAULT 'CHEST',
    view_position VARCHAR(10),
    image_size_bytes INTEGER,
    
    -- Patient demographics (anonymized)
    patient_age_range VARCHAR(20),  -- e.g., "40-50"
    patient_sex CHAR(1),
    
    -- Model information
    model_version VARCHAR(50) NOT NULL,
    model_id INTEGER REFERENCES model_metadata(id),
    
    -- Predictions
    predictions JSONB NOT NULL,  -- Raw model outputs
    calibrated_confidence JSONB NOT NULL,  -- Calibrated probabilities
    findings JSONB,  -- Structured findings
    
    -- Performance metrics
    inference_time_ms FLOAT NOT NULL,
    preprocessing_time_ms FLOAT,
    postprocessing_time_ms FLOAT,
    total_time_ms FLOAT,
    
    -- System metadata
    status inference_status DEFAULT 'completed',
    cache_hit BOOLEAN DEFAULT FALSE,
    api_version VARCHAR(20),
    client_version VARCHAR(50),
    client_ip_hash VARCHAR(64),  -- Hashed IP for audit
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    CONSTRAINT inference_logs_study_uid_check CHECK (length(study_instance_uid) > 0)
);

-- Indexes for inference_logs
CREATE INDEX idx_inference_logs_request_id ON inference_logs(request_id);
CREATE INDEX idx_inference_logs_study_uid ON inference_logs(study_instance_uid);
CREATE INDEX idx_inference_logs_patient_id_hash ON inference_logs(patient_id_hash);
CREATE INDEX idx_inference_logs_created_at ON inference_logs(created_at DESC);
CREATE INDEX idx_inference_logs_model_version ON inference_logs(model_version);
CREATE INDEX idx_inference_logs_status ON inference_logs(status);
CREATE INDEX idx_inference_logs_predictions_gin ON inference_logs USING GIN (predictions);

-- =============================================================================
-- FEEDBACK RECORDS
-- =============================================================================
CREATE TABLE feedback_records (
    id BIGSERIAL PRIMARY KEY,
    feedback_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    
    -- Reference to inference
    inference_log_id BIGINT NOT NULL REFERENCES inference_logs(id) ON DELETE CASCADE,
    request_id UUID NOT NULL REFERENCES inference_logs(request_id),
    
    -- Radiologist information (anonymized)
    radiologist_id_hash VARCHAR(64) NOT NULL,  -- Hashed radiologist ID
    radiologist_specialty VARCHAR(100),
    institution_id_hash VARCHAR(64),  -- Hashed institution ID
    
    -- Ground truth labels
    ground_truth JSONB NOT NULL,  -- {disease: true/false}
    confidence_ratings JSONB,  -- Radiologist confidence per disease
    
    -- Agreement analysis
    agreement JSONB NOT NULL,  -- {disease: true/false} - agrees with AI
    disagreement_reasons JSONB,  -- {disease: "reason"}
    
    -- Additional feedback
    comments TEXT,
    severity_assessment JSONB,  -- {disease: severity_level}
    false_positives JSONB,  -- Diseases incorrectly predicted
    false_negatives JSONB,  -- Diseases missed by AI
    
    -- Quality indicators
    image_quality_rating INTEGER CHECK (image_quality_rating BETWEEN 1 AND 5),
    explanation_quality_rating INTEGER CHECK (explanation_quality_rating BETWEEN 1 AND 5),
    clinical_usefulness_rating INTEGER CHECK (clinical_usefulness_rating BETWEEN 1 AND 5),
    
    -- Training flags
    flagged_for_training BOOLEAN DEFAULT FALSE,
    used_in_training BOOLEAN DEFAULT FALSE,
    training_dataset_version VARCHAR(50),
    status feedback_status DEFAULT 'pending',
    
    -- Review metadata
    review_time_seconds INTEGER,
    review_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for feedback_records
CREATE INDEX idx_feedback_inference_log_id ON feedback_records(inference_log_id);
CREATE INDEX idx_feedback_request_id ON feedback_records(request_id);
CREATE INDEX idx_feedback_radiologist_hash ON feedback_records(radiologist_id_hash);
CREATE INDEX idx_feedback_flagged ON feedback_records(flagged_for_training) WHERE flagged_for_training = TRUE;
CREATE INDEX idx_feedback_status ON feedback_records(status);
CREATE INDEX idx_feedback_created_at ON feedback_records(created_at DESC);
CREATE INDEX idx_feedback_ground_truth_gin ON feedback_records USING GIN (ground_truth);

-- =============================================================================
-- MODEL METADATA
-- =============================================================================
CREATE TABLE model_metadata (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) UNIQUE NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    
    -- Model artifacts
    model_path VARCHAR(500) NOT NULL,  -- S3/MinIO path
    onnx_model_path VARCHAR(500),
    config_path VARCHAR(500),
    
    -- Architecture details
    framework VARCHAR(50) NOT NULL,  -- pytorch, tensorflow
    architecture VARCHAR(100) NOT NULL,  -- densenet121, resnet50
    backbone_weights VARCHAR(200),  -- Pretrained weights source
    
    -- Capabilities
    diseases JSONB NOT NULL,  -- List of supported diseases
    input_size JSONB NOT NULL,  -- {height: 224, width: 224, channels: 3}
    num_parameters BIGINT,
    model_size_mb FLOAT,
    
    -- Training information
    training_dataset VARCHAR(200),
    training_dataset_version VARCHAR(50),
    num_training_samples INTEGER,
    num_validation_samples INTEGER,
    training_start_date DATE,
    training_end_date DATE,
    training_duration_hours FLOAT,
    
    -- Performance metrics
    validation_metrics JSONB NOT NULL,  -- {disease: {auc: 0.95, acc: 0.92}}
    test_metrics JSONB,
    calibration_metrics JSONB,
    
    -- Calibration
    calibration_method VARCHAR(50),  -- temperature, platt, isotonic
    calibration_params_path VARCHAR(500),
    
    -- Deployment
    status model_status DEFAULT 'development',
    deployed_at TIMESTAMP WITH TIME ZONE,
    deprecated_at TIMESTAMP WITH TIME ZONE,
    rollback_version VARCHAR(50),
    
    -- Compliance
    validation_report_path VARCHAR(500),
    clinical_trial_id VARCHAR(100),
    fda_cleared BOOLEAN DEFAULT FALSE,
    ce_marked BOOLEAN DEFAULT FALSE,
    
    -- MLflow integration
    mlflow_run_id VARCHAR(100),
    mlflow_experiment_id VARCHAR(100),
    
    -- Metadata
    created_by VARCHAR(100),
    notes TEXT,
    changelog TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for model_metadata
CREATE INDEX idx_model_metadata_version ON model_metadata(model_version);
CREATE INDEX idx_model_metadata_status ON model_metadata(status);
CREATE INDEX idx_model_metadata_deployed_at ON model_metadata(deployed_at DESC);
CREATE INDEX idx_model_metadata_diseases_gin ON model_metadata USING GIN (diseases);

-- =============================================================================
-- AUDIT LOGS (HIPAA Compliance)
-- =============================================================================
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    audit_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    
    -- Event information
    event_type VARCHAR(100) NOT NULL,  -- inference, feedback, model_deployment, access
    event_action VARCHAR(100) NOT NULL,  -- create, read, update, delete
    resource_type VARCHAR(100) NOT NULL,  -- inference_log, feedback, model
    resource_id VARCHAR(200),
    
    -- Actor information
    user_id_hash VARCHAR(64),
    user_role VARCHAR(50),
    client_ip_hash VARCHAR(64),
    user_agent TEXT,
    
    -- Request information
    request_id UUID,
    http_method VARCHAR(10),
    endpoint VARCHAR(200),
    request_params JSONB,
    
    -- Response information
    response_status INTEGER,
    response_time_ms FLOAT,
    
    -- PHI access tracking
    phi_accessed BOOLEAN DEFAULT FALSE,
    phi_fields JSONB,  -- List of PHI fields accessed
    access_reason VARCHAR(500),
    
    -- Security
    authentication_method VARCHAR(50),  -- jwt, api_key, oauth
    authorization_result VARCHAR(50),  -- granted, denied
    
    -- Metadata
    severity VARCHAR(20) DEFAULT 'info',  -- debug, info, warning, error, critical
    message TEXT,
    stack_trace TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for audit_logs
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_user_id_hash ON audit_logs(user_id_hash);
CREATE INDEX idx_audit_logs_request_id ON audit_logs(request_id);
CREATE INDEX idx_audit_logs_phi_accessed ON audit_logs(phi_accessed) WHERE phi_accessed = TRUE;
CREATE INDEX idx_audit_logs_severity ON audit_logs(severity);

-- =============================================================================
-- PERFORMANCE METRICS (Time-series data)
-- =============================================================================
CREATE TABLE performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    
    -- Metric identification
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,  -- counter, gauge, histogram
    
    -- Metric value
    value FLOAT NOT NULL,
    labels JSONB,  -- Additional dimensions
    
    -- Model information
    model_version VARCHAR(50),
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Time-series optimization
    CONSTRAINT performance_metrics_timestamp_check CHECK (timestamp IS NOT NULL)
);

-- Indexes for performance_metrics (optimized for time-series queries)
CREATE INDEX idx_performance_metrics_metric_name ON performance_metrics(metric_name);
CREATE INDEX idx_performance_metrics_timestamp ON performance_metrics(timestamp DESC);
CREATE INDEX idx_performance_metrics_model_version ON performance_metrics(model_version);
CREATE INDEX idx_performance_metrics_composite ON performance_metrics(metric_name, timestamp DESC);

-- Partition by month for better performance (optional, for high-volume)
-- ALTER TABLE performance_metrics PARTITION BY RANGE (timestamp);

-- =============================================================================
-- DATA DRIFT DETECTION
-- =============================================================================
CREATE TABLE data_drift_metrics (
    id BIGSERIAL PRIMARY KEY,
    
    -- Time window
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Drift statistics
    feature_name VARCHAR(100),
    distribution_stats JSONB NOT NULL,  -- mean, std, quartiles
    drift_score FLOAT,  -- KS test, PSI, etc.
    drift_detected BOOLEAN DEFAULT FALSE,
    
    -- Reference statistics
    reference_window_start TIMESTAMP WITH TIME ZONE,
    reference_stats JSONB,
    
    -- Alert
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_drift_window ON data_drift_metrics(window_end DESC);
CREATE INDEX idx_data_drift_feature ON data_drift_metrics(feature_name);
CREATE INDEX idx_data_drift_detected ON data_drift_metrics(drift_detected) WHERE drift_detected = TRUE;

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Daily inference statistics
CREATE VIEW v_daily_inference_stats AS
SELECT
    DATE(created_at) as date,
    model_version,
    COUNT(*) as total_inferences,
    AVG(inference_time_ms) as avg_inference_time_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY inference_time_ms) as p95_inference_time_ms,
    COUNT(*) FILTER (WHERE cache_hit = TRUE) as cache_hits,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_inferences
FROM inference_logs
GROUP BY DATE(created_at), model_version;

-- Model performance summary
CREATE VIEW v_model_performance AS
SELECT
    m.model_version,
    m.status,
    m.deployed_at,
    COUNT(i.id) as total_inferences,
    AVG(i.inference_time_ms) as avg_inference_time_ms,
    COUNT(f.id) as feedback_count,
    COUNT(f.id) FILTER (WHERE f.flagged_for_training = TRUE) as flagged_feedback_count
FROM model_metadata m
LEFT JOIN inference_logs i ON m.model_version = i.model_version
LEFT JOIN feedback_records f ON i.id = f.inference_log_id
GROUP BY m.model_version, m.status, m.deployed_at;

-- Feedback agreement rates
CREATE VIEW v_feedback_agreement AS
SELECT
    i.model_version,
    jsonb_object_keys(f.agreement) as disease,
    COUNT(*) as total_feedback,
    COUNT(*) FILTER (WHERE (f.agreement->>jsonb_object_keys(f.agreement))::boolean = TRUE) as agreements,
    COUNT(*) FILTER (WHERE (f.agreement->>jsonb_object_keys(f.agreement))::boolean = FALSE) as disagreements,
    ROUND(100.0 * COUNT(*) FILTER (WHERE (f.agreement->>jsonb_object_keys(f.agreement))::boolean = TRUE) / COUNT(*), 2) as agreement_rate
FROM feedback_records f
JOIN inference_logs i ON f.inference_log_id = i.id
GROUP BY i.model_version, jsonb_object_keys(f.agreement);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_inference_logs_updated_at
    BEFORE UPDATE ON inference_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_feedback_records_updated_at
    BEFORE UPDATE ON feedback_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_model_metadata_updated_at
    BEFORE UPDATE ON model_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function for audit logging
CREATE OR REPLACE FUNCTION log_model_deployment()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'production' AND (OLD.status IS NULL OR OLD.status != 'production') THEN
        INSERT INTO audit_logs (
            event_type,
            event_action,
            resource_type,
            resource_id,
            message,
            severity
        ) VALUES (
            'model_deployment',
            'deploy',
            'model',
            NEW.model_version,
            'Model ' || NEW.model_version || ' deployed to production',
            'info'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_log_model_deployment
    AFTER INSERT OR UPDATE ON model_metadata
    FOR EACH ROW
    EXECUTE FUNCTION log_model_deployment();

-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert initial model metadata
INSERT INTO model_metadata (
    model_version,
    model_name,
    model_path,
    framework,
    architecture,
    diseases,
    input_size,
    training_dataset,
    validation_metrics,
    status
) VALUES (
    'v1.0.0',
    'XRay Disease Classifier',
    's3://medscanai-models/xray/v1.0.0/model.pth',
    'pytorch',
    'densenet121',
    '["pneumonia", "tuberculosis", "cardiomegaly", "pleural_effusion", "pulmonary_edema", "fracture"]',
    '{"height": 224, "width": 224, "channels": 3}',
    'CheXpert + MIMIC-CXR',
    '{"pneumonia": {"auc": 0.92}, "tuberculosis": {"auc": 0.89}, "cardiomegaly": {"auc": 0.94}}',
    'production'
);

-- =============================================================================
-- PERMISSIONS (Least Privilege)
-- =============================================================================

-- API Service Role (read/write inference, read-only model metadata)
CREATE ROLE api_service WITH LOGIN PASSWORD 'CHANGE_ME';
GRANT SELECT, INSERT, UPDATE ON inference_logs TO api_service;
GRANT SELECT, INSERT, UPDATE ON feedback_records TO api_service;
GRANT SELECT ON model_metadata TO api_service;
GRANT INSERT ON audit_logs TO api_service;
GRANT INSERT ON performance_metrics TO api_service;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO api_service;

-- Training Service Role (read feedback, write model metadata)
CREATE ROLE training_service WITH LOGIN PASSWORD 'CHANGE_ME';
GRANT SELECT ON inference_logs TO training_service;
GRANT SELECT, UPDATE ON feedback_records TO training_service;
GRANT SELECT, INSERT, UPDATE ON model_metadata TO training_service;
GRANT INSERT ON audit_logs TO training_service;

-- Analytics Role (read-only)
CREATE ROLE analytics_user WITH LOGIN PASSWORD 'CHANGE_ME';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;

-- =============================================================================
-- MAINTENANCE
-- =============================================================================

-- Partition old data (run monthly)
-- CREATE TABLE inference_logs_archive AS SELECT * FROM inference_logs WHERE created_at < NOW() - INTERVAL '1 year';
-- DELETE FROM inference_logs WHERE created_at < NOW() - INTERVAL '1 year';

-- Vacuum and analyze
-- VACUUM ANALYZE inference_logs;
-- VACUUM ANALYZE feedback_records;

COMMENT ON TABLE inference_logs IS 'Logs all inference requests for audit and monitoring';
COMMENT ON TABLE feedback_records IS 'Radiologist feedback for continuous learning';
COMMENT ON TABLE model_metadata IS 'Model registry with versioning and deployment tracking';
COMMENT ON TABLE audit_logs IS 'HIPAA-compliant audit trail for all system access';
