-- ==================================================
-- ENTERPRISE HOSPITAL MANAGEMENT SYSTEM (HMS)
-- FULL SCHEMA DDL — PostgreSQL
-- ~85 Tables | 3NF | Soft Deletes | HIPAA/GDPR-Aware Design
-- Generated: 2025-12-14
-- ==================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- for gen_random_uuid() if preferred

-- ==================================================
-- UTILITY: AUTO-UPDATE TRIGGER
-- ==================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ==================================================
-- 1. IDENTITY & ACCESS MANAGEMENT (IAM)
-- ==================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    national_id VARCHAR(50) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMPTZ,
    failed_login_attempts SMALLINT DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_username ON users(username) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_roles_name ON roles(name) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_roles_updated BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    resource VARCHAR(64) NOT NULL,
    action VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_permissions_resource_action ON permissions(resource, action) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_permissions_updated BEFORE UPDATE ON permissions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT HULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (role_id, permission_id)
);
CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_perm ON role_permissions(permission_id);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);

CREATE TABLE auth_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET,
    user_agent TEXT,
    action VARCHAR(20) NOT NULL CHECK (action IN ('login_success', 'login_fail', 'logout', 'lockout')),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_auth_logs_user ON auth_logs(user_id);
CREATE INDEX idx_auth_logs_created ON auth_logs(created_at);

-- ==================================================
-- 2. MASTER DATA & REFERENCE TABLES
-- ==================================================

CREATE TABLE provinces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL DEFAULT 'ID',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_provinces_country ON provinces(country_code);
CREATE TRIGGER trg_provinces_updated BEFORE UPDATE ON provinces FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE cities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    province_id UUID NOT NULL REFERENCES provinces(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    postal_code_pattern VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_cities_province ON cities(province_id);
CREATE TRIGGER trg_cities_updated BEFORE UPDATE ON cities FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE religions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_religions_updated BEFORE UPDATE ON religions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE marital_statuses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code CHAR(1) NOT NULL UNIQUE,
    name VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_marital_statuses_updated BEFORE UPDATE ON marital_statuses FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE blood_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type_code VARCHAR(3) NOT NULL UNIQUE,
    description VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_blood_types_updated BEFORE UPDATE ON blood_types FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE icd10_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(10) NOT NULL UNIQUE,
    short_description VARCHAR(255) NOT NULL,
    full_description TEXT,
    category VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT true,
    effective_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_icd10_code ON icd10_codes(code) WHERE deleted_at IS NULL;
CREATE INDEX idx_icd10_category ON icd10_codes(category);
CREATE TRIGGER trg_icd10_updated BEFORE UPDATE ON icd10_codes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE icd9_procedures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(7) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_icd9_code ON icd9_procedures(code) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_icd9_updated BEFORE UPDATE ON icd9_procedures FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
    unit_type VARCHAR(20) NOT NULL CHECK (unit_type IN ('mass', 'volume', 'pressure', 'temperature', 'time', 'concentration', 'other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_units_symbol ON units(symbol);
CREATE TRIGGER trg_units_updated BEFORE UPDATE ON units FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE unit_conversions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_unit_id UUID NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
    to_unit_id UUID NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
    conversion_factor NUMERIC(18,6) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT chk_units_not_same CHECK (from_unit_id != to_unit_id)
);
CREATE INDEX idx_unit_conversions_from ON unit_conversions(from_unit_id);
CREATE INDEX idx_unit_conversions_to ON unit_conversions(to_unit_id);
CREATE TRIGGER trg_unit_conversions_updated BEFORE UPDATE ON unit_conversions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 3. HUMAN RESOURCES (STAFF)
-- ==================================================

CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(20) UNIQUE,
    description TEXT,
    head_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_departments_head ON departments(head_user_id);
CREATE TRIGGER trg_departments_updated BEFORE UPDATE ON departments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE specializations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_specializations_dept ON specializations(department_id);
CREATE TRIGGER trg_specializations_updated BEFORE UPDATE ON specializations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE staff_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    first_name VARCHAR(70) NOT NULL,
    last_name VARCHAR(70) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(10) CHECK (gender IN ('male', 'female', 'other', 'unspecified')),
    phone VARCHAR(20),
    address TEXT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    religion_id UUID REFERENCES religions(id) ON DELETE SET NULL,
    marital_status_id UUID REFERENCES marital_statuses(id) ON DELETE SET NULL,
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    photo_url TEXT,
    hire_date DATE NOT NULL,
    termination_date DATE,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    specialization_id UUID REFERENCES specializations(id) ON DELETE SET NULL,
    employee_id VARCHAR(50) UNIQUE, -- HR internal ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_staff_profiles_user ON staff_profiles(user_id);
CREATE INDEX idx_staff_profiles_city ON staff_profiles(city_id);
CREATE INDEX idx_staff_profiles_dept ON staff_profiles(department_id);
CREATE INDEX idx_staff_profiles_specialization ON staff_profiles(specialization_id);
CREATE TRIGGER trg_staff_profiles_updated BEFORE UPDATE ON staff_profiles FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL, -- e.g., 'Morning', 'Night'
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_shifts_updated BEFORE UPDATE ON shifts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE doctor_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7), -- 1=Monday
    shift_id UUID NOT NULL REFERENCES shifts(id) ON DELETE RESTRICT,
    room_id UUID, -- optional; see inpatient module
    is_available BOOLEAN NOT NULL DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_doctor_schedules_staff ON doctor_schedules(staff_id);
CREATE INDEX idx_doctor_schedules_day_shift ON doctor_schedules(day_of_week, shift_id);
CREATE TRIGGER trg_doctor_schedules_updated BEFORE UPDATE ON doctor_schedules FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE staff_shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE CASCADE,
    shift_id UUID NOT NULL REFERENCES shifts(id) ON DELETE RESTRICT,
    effective_date DATE NOT NULL,
    end_date DATE, -- NULL = ongoing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_staff_shifts_staff ON staff_shifts(staff_id);
CREATE TRIGGER trg_staff_shifts_updated BEFORE UPDATE ON staff_shifts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE staff_leaves (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE CASCADE,
    leave_type VARCHAR(30) NOT NULL CHECK (leave_type IN ('sick', 'annual', 'maternity', 'paternity', 'unpaid', 'emergency')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    reason TEXT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_staff_leaves_staff ON staff_leaves(staff_id);
CREATE INDEX idx_staff_leaves_dates ON staff_leaves(start_date, end_date);
CREATE TRIGGER trg_staff_leaves_updated BEFORE UPDATE ON staff_leaves FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 4. PATIENT MANAGEMENT
-- ==================================================

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medical_record_number VARCHAR(50) NOT NULL UNIQUE, -- MRN, hospital-generated
    national_id VARCHAR(50) UNIQUE,
    passport_number VARCHAR(50) UNIQUE,
    first_name VARCHAR(70) NOT NULL,
    last_name VARCHAR(70) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(10) CHECK (gender IN ('male', 'female', 'other', 'unspecified')),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    religion_id UUID REFERENCES religions(id) ON DELETE SET NULL,
    marital_status_id UUID REFERENCES marital_statuses(id) ON DELETE SET NULL,
    blood_type_id UUID REFERENCES blood_types(id) ON DELETE SET NULL,
    photo_url TEXT,
    is_deceased BOOLEAN NOT NULL DEFAULT false,
    deceased_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patients_mrn ON patients(medical_record_number) WHERE deleted_at IS NULL;
CREATE INDEX idx_patients_national_id ON patients(national_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_patients_city ON patients(city_id);
CREATE TRIGGER trg_patients_updated BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_emergency_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    relationship VARCHAR(50), -- e.g., 'spouse', 'father'
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    address TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_emergency_contacts_patient ON patient_emergency_contacts(patient_id);
CREATE TRIGGER trg_emergency_contacts_updated BEFORE UPDATE ON patient_emergency_contacts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_families (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    relative_patient_id UUID REFERENCES patients(id) ON DELETE SET NULL, -- link to another patient if registered
    name VARCHAR(100), -- if not a registered patient
    relationship VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patient_families_patient ON patient_families(patient_id);
CREATE INDEX idx_patient_families_relative ON patient_families(relative_patient_id);
CREATE TRIGGER trg_patient_families_updated BEFORE UPDATE ON patient_families FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE insurance_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_insurance_providers_city ON insurance_providers(city_id);
CREATE TRIGGER trg_insurance_providers_updated BEFORE UPDATE ON insurance_providers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE insurance_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id UUID NOT NULL REFERENCES insurance_providers(id) ON DELETE RESTRICT,
    policy_number VARCHAR(50) NOT NULL,
    policy_name VARCHAR(100),
    coverage_start DATE,
    coverage_end DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    copay_percentage NUMERIC(5,2), -- e.g., 20.00 = 20%
    max_coverage_amount NUMERIC(15,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_insurance_policies_provider ON insurance_policies(provider_id);
CREATE INDEX idx_insurance_policies_number ON insurance_policies(policy_number);
CREATE TRIGGER trg_insurance_policies_updated BEFORE UPDATE ON insurance_policies FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_insurances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    policy_id UUID NOT NULL REFERENCES insurance_policies(id) ON DELETE RESTRICT,
    member_id VARCHAR(50), -- ID issued by insurer
    is_primary BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'expired', 'terminated')),
    effective_date DATE NOT NULL,
    termination_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patient_insurances_patient ON patient_insurances(patient_id);
CREATE INDEX idx_patient_insurances_policy ON patient_insurances(policy_id);
CREATE TRIGGER trg_patient_insurances_updated BEFORE UPDATE ON patient_insurances FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 5. OUTPATIENT & POLYCLINIC
-- ==================================================

CREATE TABLE counters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL, -- e.g., 'Registration-1', 'Pharmacy-A'
    location VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_counters_updated BEFORE UPDATE ON counters FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE queues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    counter_id UUID REFERENCES counters(id) ON DELETE SET NULL,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    queue_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('waiting', 'in_progress', 'completed', 'cancelled')),
    service_type VARCHAR(50), -- e.g., 'registration', 'consultation', 'pharmacy'
    called_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_queues_counter ON queues(counter_id);
CREATE INDEX idx_queues_patient ON queues(patient_id);
CREATE INDEX idx_queues_status_created ON queues(status, created_at);
CREATE TRIGGER trg_queues_updated BEFORE UPDATE ON queues FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    staff_id UUID REFERENCES staff_profiles(id) ON DELETE SET NULL, -- optional if auto-assigned
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    specialization_id UUID REFERENCES specializations(id) ON DELETE SET NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes SMALLINT NOT NULL DEFAULT 30,
    status VARCHAR(20) NOT NULL CHECK (status IN ('scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show')),
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_staff ON appointments(staff_id);
CREATE INDEX idx_appointments_scheduled ON appointments(scheduled_at);
CREATE TRIGGER trg_appointments_updated BEFORE UPDATE ON appointments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE appointment_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    status_from VARCHAR(20),
    status_to VARCHAR(20) NOT NULL,
    changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_appointment_logs_appointment ON appointment_logs(appointment_id);

-- ==================================================
-- 6. MEDICAL RECORDS (EMR)
-- ==================================================

CREATE TABLE clinical_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    note_type VARCHAR(20) NOT NULL CHECK (note_type IN ('soap', 'progress', 'consult', 'discharge')),
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_clinical_notes_patient ON clinical_notes(patient_id);
CREATE INDEX idx_clinical_notes_staff ON clinical_notes(staff_id);
CREATE TRIGGER trg_clinical_notes_updated BEFORE UPDATE ON clinical_notes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_diagnoses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    icd10_id UUID NOT NULL REFERENCES icd10_codes(id) ON DELETE RESTRICT,
    diagnosed_by UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    diagnosis_date DATE NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patient_diagnoses_patient ON patient_diagnoses(patient_id);
CREATE INDEX idx_patient_diagnoses_icd ON patient_diagnoses(icd10_id);
CREATE TRIGGER trg_patient_diagnoses_updated BEFORE UPDATE ON patient_diagnoses FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_procedures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    icd9_id UUID REFERENCES icd9_procedures(id) ON DELETE SET NULL,
    procedure_name VARCHAR(255), -- if not in ICD9
    performed_by UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    procedure_date TIMESTAMPTZ NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patient_procedures_patient ON patient_procedures(patient_id);
CREATE INDEX idx_patient_procedures_icd9 ON patient_procedures(icd9_id);
CREATE TRIGGER trg_patient_procedures_updated BEFORE UPDATE ON patient_procedures FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE vital_signs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    recorded_by UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    temperature NUMERIC(5,2), -- in °C
    heart_rate SMALLINT, -- bpm
    respiratory_rate SMALLINT, -- rpm
    blood_pressure_systolic SMALLINT,
    blood_pressure_diastolic SMALLINT,
    oxygen_saturation SMALLINT, -- SpO2 %
    weight_kg NUMERIC(6,2),
    height_cm NUMERIC(5,1),
    bmi NUMERIC(4,1),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_vital_signs_patient ON vital_signs(patient_id);
CREATE INDEX idx_vital_signs_recorded ON vital_signs(recorded_at);
CREATE TRIGGER trg_vital_signs_updated BEFORE UPDATE ON vital_signs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE allergies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50), -- e.g., 'food', 'drug', 'environmental'
    severity VARCHAR(20) CHECK (severity IN ('mild', 'moderate', 'severe', 'anaphylaxis')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_allergies_updated BEFORE UPDATE ON allergies FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE patient_allergies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergy_id UUID REFERENCES allergies(id) ON DELETE SET NULL,
    allergy_name VARCHAR(100), -- if not in master list
    reaction TEXT,
    severity VARCHAR(20) CHECK (severity IN ('mild', 'moderate', 'severe', 'anaphylaxis')),
    diagnosed_by UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    diagnosed_at DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_patient_allergies_patient ON patient_allergies(patient_id);
CREATE TRIGGER trg_patient_allergies_updated BEFORE UPDATE ON patient_allergies FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE medical_histories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    history_type VARCHAR(30) NOT NULL CHECK (history_type IN ('past_illness', 'surgery', 'family', 'social', 'obstetric')),
    description TEXT NOT NULL,
    onset_date DATE,
    end_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    recorded_by UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_medical_histories_patient ON medical_histories(patient_id);
CREATE TRIGGER trg_medical_histories_updated BEFORE UPDATE ON medical_histories FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 7. INPATIENT (ADT)
-- ==================================================

CREATE TABLE buildings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE,
    address TEXT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_buildings_city ON buildings(city_id);
CREATE TRIGGER trg_buildings_updated BEFORE UPDATE ON buildings FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE wards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    building_id UUID NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE,
    ward_type VARCHAR(30) NOT NULL CHECK (ward_type IN ('general', 'icu', 'nicu', 'maternity', 'psychiatric', 'isolation')),
    capacity SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_wards_building ON wards(building_id);
CREATE TRIGGER trg_wards_updated BEFORE UPDATE ON wards FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE rooms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ward_id UUID NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
    room_number VARCHAR(20) NOT NULL,
    room_type VARCHAR(30) NOT NULL CHECK (room_type IN ('private', 'semi_private', 'ward')),
    capacity SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(ward_id, room_number)
);
CREATE INDEX idx_rooms_ward ON rooms(ward_id);
CREATE TRIGGER trg_rooms_updated BEFORE UPDATE ON rooms FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE beds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    bed_number VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'occupied', 'maintenance', 'blocked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(room_id, bed_number)
);
CREATE INDEX idx_beds_room ON beds(room_id);
CREATE INDEX idx_beds_status ON beds(status);
CREATE TRIGGER trg_beds_updated BEFORE UPDATE ON beds FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE admissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    bed_id UUID NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
    admitting_doctor_id UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    admission_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expected_discharge_date DATE,
    admission_diagnosis TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'admitted' CHECK (status IN ('admitted', 'transferred', 'discharged', 'deceased')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_admissions_patient ON admissions(patient_id);
CREATE INDEX idx_admissions_bed ON admissions(bed_id);
CREATE INDEX idx_admissions_status ON admissions(status);
CREATE TRIGGER trg_admissions_updated BEFORE UPDATE ON admissions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE bed_transfers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admission_id UUID NOT NULL REFERENCES admissions(id) ON DELETE CASCADE,
    from_bed_id UUID NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
    to_bed_id UUID NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
    transfer_reason TEXT,
    transferred_by UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    transferred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_bed_transfers_admission ON bed_transfers(admission_id);
CREATE INDEX idx_bed_transfers_from ON bed_transfers(from_bed_id);
CREATE INDEX idx_bed_transfers_to ON bed_transfers(to_bed_id);

CREATE TABLE discharge_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admission_id UUID NOT NULL REFERENCES admissions(id) ON DELETE RESTRICT,
    discharge_date TIMESTAMPTZ NOT NULL,
    discharge_condition VARCHAR(30) NOT NULL CHECK (discharge_condition IN ('improved', 'cured', 'transferred', 'deceased', 'against_advice')),
    discharge_diagnosis TEXT,
    follow_up_instructions TEXT,
    written_by UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_discharge_summaries_admission ON discharge_summaries(admission_id);
CREATE TRIGGER trg_discharge_summaries_updated BEFORE UPDATE ON discharge_summaries FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 8. PHARMACY & INVENTORY
-- ==================================================

CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city_id UUID REFERENCES cities(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_suppliers_city ON suppliers(city_id);
CREATE TRIGGER trg_suppliers_updated BEFORE UPDATE ON suppliers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE product_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    parent_id UUID REFERENCES product_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_product_categories_parent ON product_categories(parent_id);
CREATE TRIGGER trg_product_categories_updated BEFORE UPDATE ON product_categories FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    category_id UUID REFERENCES product_categories(id) ON DELETE SET NULL,
    unit_id UUID NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_name ON products(name);
CREATE TRIGGER trg_products_updated BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE inventory_stocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    location_type VARCHAR(20) NOT NULL CHECK (location_type IN ('pharmacy', 'ward', 'central_warehouse')),
    location_id UUID, -- e.g., ward_id if location_type='ward'
    quantity_available NUMERIC(18,4) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(18,4) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(product_id, location_type, location_id)
);
CREATE INDEX idx_inventory_stocks_product ON inventory_stocks(product_id);
CREATE TRIGGER trg_inventory_stocks_updated BEFORE UPDATE ON inventory_stocks FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE inventory_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_number VARCHAR(50) NOT NULL,
    expiry_date DATE NOT NULL,
    quantity NUMERIC(18,4) NOT NULL,
    purchase_price NUMERIC(15,4),
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    stock_id UUID NOT NULL REFERENCES inventory_stocks(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_inventory_batches_product ON inventory_batches(product_id);
CREATE INDEX idx_inventory_batches_expiry ON inventory_batches(expiry_date);
CREATE TRIGGER trg_inventory_batches_updated BEFORE UPDATE ON inventory_batches FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL REFERENCES inventory_batches(id) ON DELETE RESTRICT,
    from_stock_id UUID REFERENCES inventory_stocks(id) ON DELETE SET NULL,
    to_stock_id UUID REFERENCES inventory_stocks(id) ON DELETE SET NULL,
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('purchase', 'sale', 'transfer', 'adjustment', 'expiry', 'write_off')),
    quantity NUMERIC(18,4) NOT NULL,
    performed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reference_id UUID, -- e.g., prescription_id, po_id
    reference_type VARCHAR(30), -- e.g., 'prescription', 'purchase_order'
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_stock_movements_batch ON stock_movements(batch_id);
CREATE INDEX idx_stock_movements_from ON stock_movements(from_stock_id);
CREATE INDEX idx_stock_movements_to ON stock_movements(to_stock_id);

CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    ordered_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    order_status VARCHAR(20) NOT NULL CHECK (order_status IN ('draft', 'submitted', 'approved', 'received', 'cancelled')),
    expected_delivery_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE TRIGGER trg_purchase_orders_updated BEFORE UPDATE ON purchase_orders FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE po_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    ordered_quantity NUMERIC(18,4) NOT NULL,
    received_quantity NUMERIC(18,4) DEFAULT 0,
    unit_price NUMERIC(15,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_po_items_po ON po_items(po_id);
CREATE INDEX idx_po_items_product ON po_items(product_id);
CREATE TRIGGER trg_po_items_updated BEFORE UPDATE ON po_items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE prescriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    prescribed_by UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    admission_id UUID REFERENCES admissions(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'dispensed', 'cancelled', 'expired')),
    instructions TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX idx_prescriptions_prescriber ON prescriptions(prescribed_by);
CREATE TRIGGER trg_prescriptions_updated BEFORE UPDATE ON prescriptions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE prescription_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prescription_id UUID NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    dose_amount NUMERIC(10,4) NOT NULL,
    dose_unit_id UUID NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
    frequency VARCHAR(50), -- e.g., '2x daily'
    duration_days SMALLINT,
    quantity_dispensed NUMERIC(18,4) DEFAULT 0,
    instructions TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_prescription_items_rx ON prescription_items(prescription_id);
CREATE INDEX idx_prescription_items_product ON prescription_items(product_id);
CREATE TRIGGER trg_prescription_items_updated BEFORE UPDATE ON prescription_items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 9. LABORATORY & RADIOLOGY
-- ==================================================

CREATE TABLE lab_test_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_lab_test_categories_updated BEFORE UPDATE ON lab_test_categories FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE lab_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID REFERENCES lab_test_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    default_unit_id UUID REFERENCES units(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_lab_tests_category ON lab_tests(category_id);
CREATE INDEX idx_lab_tests_name ON lab_tests(name);
CREATE TRIGGER trg_lab_tests_updated BEFORE UPDATE ON lab_tests FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE lab_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    requested_by UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    admission_id UUID REFERENCES admissions(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sample_collected', 'in_progress', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_lab_requests_patient ON lab_requests(patient_id);
CREATE INDEX idx_lab_requests_status ON lab_requests(status);
CREATE TRIGGER trg_lab_requests_updated BEFORE UPDATE ON lab_requests FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE lab_request_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lab_request_id UUID NOT NULL REFERENCES lab_requests(id) ON DELETE CASCADE,
    lab_test_id UUID NOT NULL REFERENCES lab_tests(id) ON DELETE RESTRICT,
    priority VARCHAR(10) DEFAULT 'routine' CHECK (priority IN ('routine', 'urgent', 'stat')),
    clinical_info TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_lab_request_items_request ON lab_request_items(lab_request_id);
CREATE INDEX idx_lab_request_items_test ON lab_request_items(lab_test_id);
CREATE TRIGGER trg_lab_request_items_updated BEFORE UPDATE ON lab_request_items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE lab_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lab_request_item_id UUID NOT NULL REFERENCES lab_request_items(id) ON DELETE RESTRICT,
    result_value TEXT, -- supports numeric or textual results
    result_unit_id UUID REFERENCES units(id) ON DELETE SET NULL,
    reference_range VARCHAR(100), -- e.g., '4.0 - 11.0'
    abnormal_flag BOOLEAN DEFAULT false,
    verified_by UUID REFERENCES staff_profiles(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_lab_results_request_item ON lab_results(lab_request_item_id);
CREATE INDEX idx_lab_results_verified ON lab_results(verified_by);
CREATE TRIGGER trg_lab_results_updated BEFORE UPDATE ON lab_results FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- 10. BILLING & FINANCE
-- ==================================================

CREATE TABLE service_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_service_categories_updated BEFORE UPDATE ON service_categories FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID NOT NULL REFERENCES service_categories(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE, -- e.g., CPT, HCPCS, or internal code
    description TEXT,
    default_price NUMERIC(15,2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_services_category ON services(category_id);
CREATE INDEX idx_services_code ON services(code);
CREATE TRIGGER trg_services_updated BEFORE UPDATE ON services FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE price_components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    component_name VARCHAR(100) NOT NULL, -- e.g., 'facility_fee', 'professional_fee'
    amount NUMERIC(15,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_price_components_service ON price_components(service_id);
CREATE TRIGGER trg_price_components_updated BEFORE UPDATE ON price_components FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE payment_methods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE, -- e.g., 'cash', 'credit_card', 'insurance'
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE TRIGGER trg_payment_methods_updated BEFORE UPDATE ON payment_methods FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE cash_registers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL,
    opened_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    closed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    opening_balance NUMERIC(15,2) NOT NULL DEFAULT 0,
    closing_balance NUMERIC(15,2),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'mismatch')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_cash_registers_opened_by ON cash_registers(opened_by);
CREATE TRIGGER trg_cash_registers_updated BEFORE UPDATE ON cash_registers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'billed', 'paid', 'partially_paid', 'voided')),
    total_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    insurance_coverage_amount NUMERIC(18,2) DEFAULT 0,
    patient_responsibility NUMERIC(18,2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_invoices_patient ON invoices(patient_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE TRIGGER trg_invoices_updated BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE invoice_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    service_id UUID REFERENCES services(id) ON DELETE SET NULL,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    description VARCHAR(255) NOT NULL,
    quantity NUMERIC(10,2) NOT NULL DEFAULT 1,
    unit_price NUMERIC(15,2) NOT NULL,
    total_price NUMERIC(18,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CHECK ((service_id IS NOT NULL AND product_id IS NULL) OR (service_id IS NULL AND product_id IS NOT NULL))
);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX idx_invoice_items_service ON invoice_items(service_id);
CREATE INDEX idx_invoice_items_product ON invoice_items(product_id);
CREATE TRIGGER trg_invoice_items_updated BEFORE UPDATE ON invoice_items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    payment_method_id UUID NOT NULL REFERENCES payment_methods(id) ON DELETE RESTRICT,
    cash_register_id UUID REFERENCES cash_registers(id) ON DELETE SET NULL,
    amount NUMERIC(18,2) NOT NULL,
    payment_reference VARCHAR(100), -- e.g., transaction ID
    paid_by_name VARCHAR(100), -- if not patient
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_method ON payments(payment_method_id);
CREATE TRIGGER trg_payments_updated BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==================================================
-- END OF HMS FULL SCHEMA (~85 tables)
-- ==================================================