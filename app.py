from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finsta",
                             charset="utf8mb4",
                             port=3308,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home(note=None):
    #session.pop('_flashes', None)
    return render_template("home.html", username=session["username"])


@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO photo (timestamp, filePath) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)


#queries

@app.route("/addFriend", methods=['GET', 'POST'])
def addFriend():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)


    if request.method=='POST':
        user = session["username"]

        friend = request.form['friend'].lower()
        fg = request.form['fg']

        q = "SELECT * FROM belong WHERE groupOwner = %s AND username = %s AND groupName = %s"
        cursor = connection.cursor()
        cursor.execute(q, (user, friend, fg))
        check = cursor.fetchone()
        cursor.close()

        q = "SELECT * FROM person WHERE username=%s"
        cursor = connection.cursor()
        cursor.execute(q, friend)
        check2 = cursor.fetchone()
        cursor.close()

        q = "SELECT * FROM closefriendgroup WHERE groupName=%s"
        cursor = connection.cursor()
        cursor.execute(q, fg)
        check3 = cursor.fetchone()
        cursor.close()

        if check:
            note = "Email already in Friend group"
            flash("already in group")
            return home(note)

        if not check2:
            note = "Does not exist"
            flash("user does not exist")
            return home(note)

        if not check3:
            note = "Does not exist"
            flash("group does not exist")
            return home(note)

        q = "INSERT INTO belong(username, groupOwner, groupName) VALUES (%s, %s, %s)"
        cursor = connection.cursor()
        cursor.execute(q, (friend, user, fg))
        connection.commit()
        cursor.close()
        note = "Friend has been added."
        flash("added")
        return home(note)

    return render_template('addFriend.html')

@app.route("/createGroup", methods=['GET', 'POST'])
def createGroup():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)


    if request.method=='POST':
        user = session["username"]

        fg = request.form['newfg']

        q = "SELECT * FROM closefriendgroup WHERE groupOwner = %s AND groupName = %s"
        cursor = connection.cursor()
        cursor.execute(q, (user, fg))
        check = cursor.fetchone()
        cursor.close()

        if check:
            #note = "Can't reuse group name"
            flash("cannot resuse group name")
            return home()

        q="INSERT INTO closefriendgroup(groupOwner, groupName) VALUES (%s, %s)"
        cursor = connection.cursor()
        cursor.execute(q, (user, fg))
        connection.commit()
        cursor.close()
        q = "INSERT INTO belong(username, groupOwner, groupName) VALUES (%s, %s, %s)"
        cursor = connection.cursor()
        cursor.execute(q, (user, user, fg))
        connection.commit()
        cursor.close()
        #note = "Group has been created."
        flash('Group has been created')
        return home()

    return render_template('createGroup.html')

@app.route("/showPosts", methods=['GET'])
def showPosts():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    user = session['username']
    cursor = connection.cursor()
    query = 'SELECT timestamp, photoOwner, caption, filePath FROM photo ORDER BY timestamp'
    #change the query also make it so it shows the actual picture
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()

    return render_template('showPosts.html', content=data)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.debug=True

    app.run()
