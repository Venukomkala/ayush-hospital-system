from flask import Flask, render_template, request, jsonify
import sqlite3
import csv

app = Flask(__name__)

# --------------------- DATABASE INIT ---------------------
def init_db():
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()
    # Patients table
    c.execute('''CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    address TEXT,
                    contact TEXT,
                    admission_date TEXT,
                    room TEXT
                )''')
    
    # Prescriptions table
    c.execute('''CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    disease TEXT,
                    namaste_code TEXT,
                    icd_code TEXT,
                    description TEXT,
                    medication TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(id)
                )''')
    conn.commit()
    
    # Ensure 'biomedicine' column exists (for older databases)
    c.execute("PRAGMA table_info(prescriptions)")
    columns = [col[1] for col in c.fetchall()]
    if 'biomedicine' not in columns:
        c.execute("ALTER TABLE prescriptions ADD COLUMN biomedicine TEXT")
        conn.commit()
    
    conn.close()

init_db()

# --------------------- LOAD DISEASE DATA ---------------------
DISEASE_DATA = []
with open('disease_data.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        DISEASE_DATA.append({
            'english_name': row.get('English Name', '').strip(),
            'ayush_name': row.get('Ayush Name', '').strip(),
            'namaste': row.get('NAMASTE Code', '').strip(),
            'icd11': row.get('ICD-11 Code', '').strip(),
            'biomedicine': row.get('Biomedicine', '').strip()
        })

# --------------------- ROUTES ---------------------

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# ----------------- ADD PATIENT -----------------
@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        data = request.form
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()
        c.execute('''INSERT INTO patients (name, age, gender, address, contact, admission_date, room)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (data['name'], data['age'], data['gender'], data['address'],
                      data['contact'], data['admission_date'], data['room']))
        conn.commit()
        patient_id = c.lastrowid
        conn.close()
        return jsonify({'status': 'success', 'patient_id': patient_id})
    else:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()
        c.execute("SELECT MAX(id) FROM patients")
        max_id = c.fetchone()[0]
        next_id = (max_id or 0) + 1
        conn.close()
        return render_template('add_patient_form.html', patient_id=next_id)

# ----------------- PRESCRIPTION -----------------
@app.route('/prescription')
def prescription():
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM patients")
    patients = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]
    conn.close()
    return render_template('prescription.html', patients=patients)

@app.route('/save_prescription', methods=['POST'])
def save_prescription():
    try:
        data = request.get_json(force=True)
        patient_id = int(data.get('patientId', 0))
        disease = data.get('disease', '').strip()
        namaste_code = data.get('namaste', '').strip()
        icd_code = data.get('icd11', '').strip()
        biomedicine = data.get('biomedicine', '').strip()
        description = data.get('description', '').strip()
        medication = data.get('medication', '').strip()

        if not patient_id or not disease:
            return jsonify({'status': 'error', 'message': 'Patient and disease are required'})

        conn = sqlite3.connect('patients.db')
        c = conn.cursor()
        c.execute('''INSERT INTO prescriptions 
                     (patient_id, disease, namaste_code, icd_code, biomedicine, description, medication)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (patient_id, disease, namaste_code, icd_code, biomedicine, description, medication))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})

    except Exception as e:
        print("Error saving prescription:", e)
        return jsonify({'status': 'error', 'message': str(e)})

# ----------------- DISEASE SUGGESTIONS -----------------
@app.route('/disease_suggestions')
def disease_suggestions():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])

    results = []
    for disease in DISEASE_DATA:
        eng = disease['english_name'].lower()
        ayu = disease['ayush_name'].lower()
        if query in eng or query in ayu:
            # Show full display including English name first
            combined_display = f"{disease['english_name']} | {disease['ayush_name']} | {disease['namaste']} | {disease['icd11']} | {disease['biomedicine']}"
            results.append({
                'english_name': disease['english_name'],
                'ayush_name': disease['ayush_name'],
                'namaste': disease['namaste'],
                'icd11': disease['icd11'],
                'biomedicine': disease['biomedicine'],
                'display': combined_display
            })

    return jsonify(results[:10])

# ----------------- PATIENT RECORDS -----------------
@app.route('/patient_records')
def patient_records():
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()
    c.execute('''
        SELECT p.id, p.name, p.age, p.contact,
               (SELECT disease FROM prescriptions pr WHERE pr.patient_id = p.id ORDER BY pr.id DESC LIMIT 1) AS disease
        FROM patients p
        ORDER BY p.id
    ''')
    patients = [
        {'id': row[0], 'name': row[1], 'age': row[2], 'contact': row[3], 'disease': row[4] or ''}
        for row in c.fetchall()
    ]
    conn.close()
    return render_template('patient_records.html', patients=patients)

# ----------------- DIAGNOSIS FUNCTIONALITY -----------------
@app.route('/diagnosis')
def diagnosis():
    return render_template('diagnosis.html')

@app.route('/get_diagnosis')
def get_diagnosis():
    conn = sqlite3.connect('patients.db')
    c = conn.cursor()
    c.execute('''
        SELECT p.id, p.name, p.age, p.gender, p.contact, p.address,
               (SELECT disease FROM prescriptions pr WHERE pr.patient_id = p.id ORDER BY pr.id DESC LIMIT 1) AS disease
        FROM patients p
        ORDER BY p.id
    ''')
    patients = [
        {'id': row[0], 'name': row[1], 'age': row[2], 'gender': row[3], 'contact': row[4],
         'address': row[5], 'disease': row[6] or ''}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(patients)

# ----------------- DELETE PATIENT -----------------
@app.route('/delete_patient/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    try:
        conn = sqlite3.connect('patients.db')
        c = conn.cursor()
        c.execute('DELETE FROM prescriptions WHERE patient_id=?', (patient_id,))
        c.execute('DELETE FROM patients WHERE id=?', (patient_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ----------------- NEW: DISEASE DATA API -----------------
@app.route('/api/diseases')
def api_diseases():
    return jsonify(DISEASE_DATA)

# ----------------- RUN APP -----------------
if __name__ == '__main__':
    app.run(debug=True)
