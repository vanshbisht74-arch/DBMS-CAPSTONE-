import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'hospital.db'
SCHEMA_PATH = BASE_DIR / 'hospital_db.sql'


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))


RBAC_ROLES = {
    'admin': {'read', 'register_patient', 'book_appointment', 'payment', 'insurance'},
    'receptionist': {'read', 'register_patient', 'book_appointment', 'payment'},
    'doctor': {'read'}
}


def allowed(role, action):
    return action in RBAC_ROLES.get(role, set())


UNIT2_QUERIES = {
    'inner_join': {
        'title': 'INNER JOIN — Patients with appointments',
        'sql': '''SELECT p.full_name AS patient, d.full_name AS doctor, a.appointment_date, a.status
FROM patients p JOIN appointments a ON p.patient_id = a.patient_id
JOIN doctors d ON d.doctor_id = a.doctor_id ORDER BY a.appointment_date;'''
    },
    'outer_join': {
        'title': 'LEFT JOIN — All patients, including those without appointments',
        'sql': '''SELECT p.full_name, COALESCE(a.status, 'No appointment') AS appointment_status
FROM patients p LEFT JOIN appointments a ON p.patient_id = a.patient_id
ORDER BY p.patient_id;'''
    },
    'self_join': {
        'title': 'SELF JOIN — Doctor and supervising doctor hierarchy',
        'sql': '''SELECT d.full_name AS doctor, COALESCE(s.full_name, 'Department Head') AS reports_to
FROM doctors d LEFT JOIN doctors s ON d.supervisor_id = s.doctor_id;'''
    },
    'subquery': {
        'title': 'SUBQUERY — Bills above the hospital average',
        'sql': '''SELECT bill_id, patient_id, total_amount, paid_amount, (total_amount-paid_amount) AS due_amount
FROM bills WHERE total_amount > (SELECT AVG(total_amount) FROM bills);'''
    },
    'set_op': {
        'title': 'SET OPERATION — Patients with bills EXCEPT patients with completed payments',
        'sql': '''SELECT patient_id FROM bills
EXCEPT
SELECT b.patient_id FROM bills b JOIN payments p ON p.bill_id=b.bill_id;'''
    },
    'view': {'title': 'VIEW — Patient care summary', 'sql': 'SELECT * FROM v_patient_summary;'},
    'cte_window': {
        'title': 'CTE + WINDOW FUNCTIONS — Rank doctors by appointment load',
        'sql': '''WITH doctor_stats AS (
 SELECT d.doctor_id, d.full_name, d.specialty, COUNT(a.appointment_id) AS appointment_count
 FROM doctors d LEFT JOIN appointments a ON a.doctor_id=d.doctor_id
 GROUP BY d.doctor_id, d.full_name, d.specialty
)
SELECT *, RANK() OVER (ORDER BY appointment_count DESC) AS workload_rank,
       SUM(appointment_count) OVER (ORDER BY appointment_count DESC) AS running_appointments
FROM doctor_stats;'''
    }
}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/dashboard')
def dashboard():
    with get_conn() as conn:
        patients = conn.execute('''SELECT patient_id, medical_record_no, full_name, age, phone FROM patients ORDER BY patient_id''').fetchall()
        appointments = conn.execute('''SELECT a.appointment_id, p.full_name AS patient, d.full_name AS doctor,
            a.appointment_date, a.status, a.version FROM appointments a
            JOIN patients p ON p.patient_id=a.patient_id JOIN doctors d ON d.doctor_id=a.doctor_id
            ORDER BY a.appointment_date DESC LIMIT 15''').fetchall()
        bills = conn.execute('''SELECT b.bill_id, p.full_name AS patient, b.total_amount, b.paid_amount,
            b.total_amount-b.paid_amount AS due_amount, b.status FROM bills b
            JOIN patients p ON p.patient_id=b.patient_id ORDER BY b.bill_id DESC LIMIT 12''').fetchall()
        payments = conn.execute('''SELECT py.payment_id, py.bill_id, p.full_name AS patient, py.amount, py.payment_method, py.paid_at
            FROM payments py JOIN bills b ON b.bill_id=py.bill_id JOIN patients p ON p.patient_id=b.patient_id
            ORDER BY py.payment_id DESC LIMIT 10''').fetchall()
        audits = conn.execute('SELECT * FROM audit_logs ORDER BY log_id DESC LIMIT 10').fetchall()
        stats = {
            'patients': conn.execute('SELECT COUNT(*) FROM patients').fetchone()[0],
            'appointments': conn.execute("SELECT COUNT(*) FROM appointments WHERE status='SCHEDULED'").fetchone()[0],
            'revenue': conn.execute('SELECT COALESCE(SUM(amount),0) FROM payments').fetchone()[0],
            'doctors': conn.execute('SELECT COUNT(*) FROM doctors').fetchone()[0]
        }
        return jsonify({'stats': stats, 'patients': [dict(x) for x in patients],
                        'appointments': [dict(x) for x in appointments], 'bills': [dict(x) for x in bills],
                        'payments': [dict(x) for x in payments], 'audits': [dict(x) for x in audits]})


@app.route('/api/patient', methods=['POST'])
def add_patient():
    role = request.headers.get('X-Role', 'receptionist')
    if not allowed(role, 'register_patient'):
        return jsonify({'error': f"RBAC denied: {role} cannot register patients"}), 403
    data = request.get_json(force=True)
    try:
        with get_conn() as conn:
            cur = conn.execute('INSERT INTO patients (medical_record_no, full_name, age, gender, phone, email) VALUES (?,?,?,?,?,?)',
                (data['medical_record_no'].strip(), data['full_name'].strip(), int(data['age']), data['gender'], data.get('phone',''), data.get('email','')))
            return jsonify({'status': f"Patient registered successfully (Patient ID {cur.lastrowid})"})
    except sqlite3.IntegrityError as exc:
        return jsonify({'error': f'Could not register patient: {exc}'}), 400
    except (KeyError, ValueError):
        return jsonify({'error': 'Provide a valid medical record number, name, age and gender.'}), 400


@app.route('/api/appointment', methods=['POST'])
def book_appointment():
    role = request.headers.get('X-Role', 'receptionist')
    if not allowed(role, 'book_appointment'):
        return jsonify({'error': f"RBAC denied: {role} cannot book appointments"}), 403
    data = request.get_json(force=True)
    try:
        with get_conn() as conn:
            cur = conn.execute('''INSERT INTO appointments (patient_id, doctor_id, appointment_date, reason)
                VALUES (?,?,?,?)''', (int(data['patient_id']), int(data['doctor_id']), data['appointment_date'], data.get('reason','General consultation')))
            return jsonify({'status': f'Appointment #{cur.lastrowid} scheduled successfully.'})
    except (sqlite3.IntegrityError, KeyError, ValueError) as exc:
        return jsonify({'error': f'Appointment could not be scheduled: {exc}'}), 400


@app.route('/api/payment', methods=['POST'])
def make_payment():
    role = request.headers.get('X-Role', 'receptionist')
    if not allowed(role, 'payment'):
        return jsonify({'error': f"RBAC denied: {role} cannot record payments"}), 403
    data = request.get_json(force=True)
    try:
        bill_id, amount = int(data['bill_id']), float(data['amount'])
        if amount <= 0:
            raise ValueError('Payment amount must be positive.')
        conn = get_conn()
        try:
            conn.execute('BEGIN IMMEDIATE')
            bill = conn.execute('SELECT total_amount, paid_amount, version FROM bills WHERE bill_id=?', (bill_id,)).fetchone()
            if not bill:
                raise ValueError('Bill not found.')
            if amount > bill['total_amount'] - bill['paid_amount']:
                raise ValueError('Payment exceeds the outstanding bill amount.')
            cur = conn.execute('''UPDATE bills SET paid_amount=paid_amount+?, version=version+1,
                status=CASE WHEN paid_amount+? >= total_amount THEN 'PAID' ELSE 'PARTIALLY_PAID' END
                WHERE bill_id=? AND version=?''', (amount, amount, bill_id, bill['version']))
            if cur.rowcount != 1:
                raise ValueError('Concurrent bill update detected; retry the payment.')
            conn.execute('INSERT INTO payments (bill_id, amount, payment_method) VALUES (?,?,?)',
                         (bill_id, amount, data.get('payment_method','CASH')))
            conn.commit()
            return jsonify({'status': f'Payment of ₹{amount:,.2f} recorded. Bill and payment ledger committed atomically.'})
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except (KeyError, ValueError, sqlite3.IntegrityError) as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/api/insurance-adjustment', methods=['POST'])
def insurance_adjustment():
    role = request.headers.get('X-Role', 'admin')
    if not allowed(role, 'insurance'):
        return jsonify({'error': 'RBAC denied: only Admin can run the batch insurance adjustment.'}), 403
    # Demonstration batch process: apply a 5% concession to outstanding balances
    # for bills explicitly marked insurance_eligible=1.
    with get_conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute("SELECT bill_id, total_amount, paid_amount FROM bills WHERE insurance_eligible=1 AND status!='PAID'").fetchall()
        count = 0
        for bill in rows:
            due = bill['total_amount'] - bill['paid_amount']
            concession = round(due * 0.05, 2)
            conn.execute('UPDATE bills SET total_amount=total_amount-?, version=version+1 WHERE bill_id=?', (concession, bill['bill_id']))
            count += 1
        conn.commit()
    return jsonify({'status': f'Batch cursor processed {count} eligible bills; 5% concession applied to outstanding amounts.'})


@app.route('/api/demo-savepoint', methods=['POST'])
def savepoint_demo():
    role = request.headers.get('X-Role', 'admin')
    if not allowed(role, 'insurance'):
        return jsonify({'error': 'RBAC denied: only Admin can run the savepoint demonstration.'}), 403
    with get_conn() as conn:
        bill = conn.execute('SELECT bill_id, total_amount, paid_amount FROM bills WHERE status != "PAID" ORDER BY bill_id LIMIT 1').fetchone()
        if not bill:
            return jsonify({'error': 'No unpaid bill is available for the savepoint demo.'}), 400
        conn.execute('BEGIN IMMEDIATE')
        demo_amount = min(100.0, bill['total_amount'] - bill['paid_amount'])
        conn.execute('UPDATE bills SET paid_amount=paid_amount+?, version=version+1 WHERE bill_id=?', (demo_amount, bill['bill_id']))
        conn.execute('SAVEPOINT before_error')
        conn.execute('UPDATE bills SET total_amount=total_amount+999999, version=version+1 WHERE bill_id=?', (bill['bill_id'],))
        conn.execute('ROLLBACK TO SAVEPOINT before_error')
        conn.execute('INSERT INTO payments (bill_id, amount, payment_method) VALUES (?,?,?)', (bill['bill_id'], demo_amount, 'DEMO'))
        conn.commit()
    return jsonify({'status': f'Savepoint demo: invalid ₹999,999 update rolled back; valid ₹{demo_amount:.2f} payment committed.'})


@app.route('/api/unit2/<query_key>')
def run_unit2_query(query_key):
    query = UNIT2_QUERIES.get(query_key)
    if not query:
        return jsonify({'error': 'Unknown query'}), 404
    with get_conn() as conn:
        cur = conn.execute(query['sql'])
        columns = [x[0] for x in cur.description]
        return jsonify({'title': query['title'], 'sql': query['sql'], 'columns': columns,
                        'rows': [dict(row) for row in cur.fetchall()]})


@app.route('/api/search')
def search_patient():
    mrn = request.args.get('mrn', '')
    with get_conn() as conn:
        rows = conn.execute('SELECT patient_id, medical_record_no, full_name, age, gender, phone FROM patients WHERE medical_record_no=?', (mrn,)).fetchall()
        return jsonify([dict(row) for row in rows])


@app.route('/api/explain/<mode>')
def explain_plan(mode):
    sql = ("SELECT * FROM patients WHERE medical_record_no='MRN1001';" if mode == 'indexed'
           else "SELECT * FROM appointments WHERE status='SCHEDULED';")
    with get_conn() as conn:
        plan = conn.execute('EXPLAIN QUERY PLAN ' + sql).fetchall()
        return jsonify({'sql': sql, 'plan': [dict(row) for row in plan]})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
