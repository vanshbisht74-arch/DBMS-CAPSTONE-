PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
 patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
 medical_record_no TEXT UNIQUE NOT NULL,
 full_name TEXT NOT NULL,
 age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 120),
 gender TEXT NOT NULL CHECK(gender IN ('Female','Male','Other')),
 phone TEXT, email TEXT,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS doctors (
 doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
 full_name TEXT NOT NULL,
 specialty TEXT NOT NULL,
 department TEXT NOT NULL,
 supervisor_id INTEGER REFERENCES doctors(doctor_id)
);
CREATE TABLE IF NOT EXISTS appointments (
 appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
 patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
 doctor_id INTEGER NOT NULL REFERENCES doctors(doctor_id),
 appointment_date TEXT NOT NULL,
 reason TEXT,
 status TEXT NOT NULL DEFAULT 'SCHEDULED' CHECK(status IN ('SCHEDULED','COMPLETED','CANCELLED')),
 version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS bills (
 bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
 patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
 total_amount REAL NOT NULL CHECK(total_amount >= 0),
 paid_amount REAL NOT NULL DEFAULT 0 CHECK(paid_amount >= 0 AND paid_amount <= total_amount),
 insurance_eligible INTEGER NOT NULL DEFAULT 0 CHECK(insurance_eligible IN (0,1)),
 status TEXT NOT NULL DEFAULT 'UNPAID' CHECK(status IN ('UNPAID','PARTIALLY_PAID','PAID')),
 version INTEGER NOT NULL DEFAULT 1,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
 payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
 bill_id INTEGER NOT NULL REFERENCES bills(bill_id),
 amount REAL NOT NULL CHECK(amount > 0),
 payment_method TEXT NOT NULL CHECK(payment_method IN ('CASH','CARD','UPI','INSURANCE','DEMO')),
 paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_logs (
 log_id INTEGER PRIMARY KEY AUTOINCREMENT,
 bill_id INTEGER NOT NULL,
 old_paid_amount REAL NOT NULL,
 new_paid_amount REAL NOT NULL,
 changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO patients(patient_id,medical_record_no,full_name,age,gender,phone,email) VALUES
(1,'MRN1001','Aarav Sharma',28,'Male','9876543210','aarav@example.com'),
(2,'MRN1002','Priya Nair',34,'Female','9876543211','priya@example.com'),
(3,'MRN1003','Rohan Verma',46,'Male','9876543212','rohan@example.com'),
(4,'MRN1004','Meera Iyer',22,'Female','9876543213','meera@example.com'),
(5,'MRN1005','Kabir Singh',61,'Male','9876543214','kabir@example.com');
INSERT OR IGNORE INTO doctors(doctor_id,full_name,specialty,department,supervisor_id) VALUES
(1,'Dr. Ananya Rao','Cardiology','Cardiology',NULL),
(2,'Dr. Vikram Mehta','General Medicine','Medicine',NULL),
(3,'Dr. Sana Khan','Dermatology','Dermatology',2),
(4,'Dr. Arjun Kapoor','Orthopedics','Orthopedics',2);
INSERT OR IGNORE INTO appointments(appointment_id,patient_id,doctor_id,appointment_date,reason,status) VALUES
(1,1,1,'2026-11-25 10:00','Routine cardiac consultation','SCHEDULED'),
(2,2,2,'2026-11-25 11:30','Fever and fatigue','SCHEDULED'),
(3,3,4,'2026-11-26 09:30','Knee pain','SCHEDULED'),
(4,4,3,'2026-11-24 14:00','Skin consultation','COMPLETED');
INSERT OR IGNORE INTO bills(bill_id,patient_id,total_amount,paid_amount,insurance_eligible,status) VALUES
(1,1,4500,1500,1,'PARTIALLY_PAID'),
(2,2,1800,1800,0,'PAID'),
(3,3,12500,0,1,'UNPAID'),
(4,4,2500,1000,0,'PARTIALLY_PAID'),
(5,5,3200,0,1,'UNPAID');
INSERT OR IGNORE INTO payments(payment_id,bill_id,amount,payment_method) VALUES
(1,1,1500,'UPI'),(2,2,1800,'CARD'),(3,4,1000,'CASH');

CREATE VIEW IF NOT EXISTS v_patient_summary AS
SELECT p.patient_id,p.medical_record_no,p.full_name,COUNT(DISTINCT a.appointment_id) AS total_appointments,
       COUNT(DISTINCT b.bill_id) AS total_bills,COALESCE(SUM(DISTINCT b.total_amount),0) AS billed_amount
FROM patients p LEFT JOIN appointments a ON a.patient_id=p.patient_id
LEFT JOIN bills b ON b.patient_id=p.patient_id GROUP BY p.patient_id,p.medical_record_no,p.full_name;

CREATE TRIGGER IF NOT EXISTS trg_audit_bill_payment
AFTER UPDATE OF paid_amount ON bills
FOR EACH ROW WHEN OLD.paid_amount <> NEW.paid_amount
BEGIN
 INSERT INTO audit_logs(bill_id,old_paid_amount,new_paid_amount)
 VALUES(OLD.bill_id,OLD.paid_amount,NEW.paid_amount);
END;

CREATE INDEX IF NOT EXISTS idx_patient_mrn ON patients(medical_record_no);
CREATE INDEX IF NOT EXISTS idx_appointment_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_payment_bill ON payments(bill_id);
