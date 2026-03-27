from flask import Flask, send_file
import io

app = Flask(__name__)

@app.route('/test-csv')
def test_csv():
    # Create a simple CSV file
    output = io.StringIO()
    output.write("name,age\nJohn,30\nJane,25")
    
    # Create a file-like object
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name='test.csv'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)
