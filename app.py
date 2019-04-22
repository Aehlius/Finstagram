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
        username = requestData["username"].lower()
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
        username = requestData["username"].lower()
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

@app.route("/uploader", methods=["POST","GET"])
@login_required
def uploader():
    user = session["username"].lower()
    q = "SELECT DISTINCT groupName, groupOwner FROM closefriendgroup NATURAL JOIN " \
        "belong WHERE closefriendgroup.groupOwner=%s OR (belong.username=%s AND acceptedReq=1)"
    cursor = connection.cursor()
    cursor.execute(q,(user,user))
    groups = cursor.fetchall()
    cursor.close()

    #q = "SELECT * FROM belong WHERE username=%s"
    #cursor = connection.cursor()
    #cursor.execute(q,user)
    #groups = cursor.fetchall()
    #cursor.close()


    return render_template("uploader.html", groups=groups)

@app.route("/uploadImage", methods=["POST","GET"])
@login_required
def upload_image():
    if request.files:
        user = session["username"].lower()
        q = "SELECT * FROM closefriendgroup"
        cursor = connection.cursor()
        cursor.execute(q)
        owns = cursor.fetchall()
        cursor.close()

        q = "SELECT * FROM belong WHERE username=%s"
        cursor = connection.cursor()
        cursor.execute(q, user)
        groups = cursor.fetchall()
        cursor.close()

        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)

        caption=request.form['caption']
        share_to = request.form.getlist('share_to')
        insert = 'INSERT into photo(photoOwner, timestamp, filePath, caption, allFollowers) \
        	VALUES (%s, %s, %s, %s, %s)'
        if share_to[0] == 'public':
                cursor=connection.cursor()
                cursor.execute(insert, (user, time.strftime('%Y-%m-%d %H:%M:%S'), image_name,caption, 1))
                connection.commit()
                cursor.close()

        else:
            cursor = connection.cursor()
            cursor.execute(insert, (user, time.strftime('%Y-%m-%d %H:%M:%S'), image_name, caption, 0))
            connection.commit()
            query = 'SELECT max(photoID) FROM photo'
            cursor.execute(query)
            max_item_id = cursor.fetchone()
            for fg in share_to:
                pg = fg.split('-')
                groupName=pg[0]
                groupOwner=pg[1]
                insert = 'INSERT into share(groupName, groupOwner, photoID) VALUES(%s, %s, %s)'
                cursor.execute(insert, (groupName, groupOwner, max_item_id['max(photoID)']))
                connection.commit()
            cursor.close()

        #image_file = request.files.get("imageToUpload", "")
        #image_name = image_file.filename
        #filepath = os.path.join(IMAGES_DIR, image_name)
        #image_file.save(filepath)
        #query = "INSERT INTO photo (timestamp, filePath, photoOwner) VALUES (%s, %s, %s)"
        #with connection.cursor() as cursor:
        #    cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, user))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message, owns=owns, groups=groups)
    else:
        user = session["username"]
        q = "SELECT * FROM closefriendgroup"
        cursor = connection.cursor()
        cursor.execute(q)
        owns = cursor.fetchall()
        cursor.close()
        q = "SELECT * FROM belong WHERE username=%s"
        cursor = connection.cursor()
        cursor.execute(q, user)
        groups = cursor.fetchall()
        cursor.close()

        message = "Failed to upload image."
        return render_template("upload.html", message=message, owns=owns, groups=groups)


#queries

@app.route("/addFriend", methods=['GET', 'POST'])
def addFriend():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)


    if request.method=='POST':
        user = session["username"].lower()

        friend = request.form['friend'].lower()
        fg = request.form['fg'].lower()

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

        q = "INSERT INTO belong(username, groupOwner, groupName, acceptedReq, reqResponded) VALUES (%s, %s, %s,0,0)"
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
        user = session["username"].lower()

        fg = request.form['newfg'].lower()

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
        q = "INSERT INTO belong(username, groupOwner, groupName, acceptedReq, reqResponded) VALUES (%s, %s, %s, 1, 1)"
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

    user = session['username'].lower()
    cursor = connection.cursor()
    query = 'SELECT photoID, timestamp, caption, photoOwner, filePath FROM photo WHERE photoOwner=%s ' \
        'OR photoID IN (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.groupName=%s AND ' \
'belong.acceptedReq=1) OR photoID IN (SELECT photoID FROM follow WHERE follow.followeeUsername=%s and follow.acceptedFollow=1)'
    cursor.execute(query, (user, user, user))
    data = cursor.fetchall()
    cursor.close()

    cursor=connection.cursor()
    tagquery='SELECT * FROM tag'
    cursor.execute(tagquery)
    tags=cursor.fetchall()
    cursor.close()

    #cursor = connection.cursor()
    #query = 'SELECT DISTINCT timestamp, photoOwner, caption, filePath FROM photo NATURAL JOIN share NATURAL JOIN ' \
    #        'belong WHERE photo.photoID=share.photoID AND belong.username=%s ORDER BY timestamp'
    #cursor.execute(query, user)
    #data2 = cursor.fetchall()
    #cursor.close()

    #some sort of query for groups
    #cursor = connection.cursor()
    #query = 'SELECT DISTINCT timestamp, photoOwner, caption, filePath FROM photo NATURAL JOIN follow WHERE ' \
    #        'photo.allFollowers=1 OR follow.acceptedFollow=1 ORDER BY timestamp'
    #cursor.execute(query)
    #data3 = cursor.fetchall()
    #cursor.close()

   #SELECT DISTINT photoID FROM photo NATURAL JOIN share NATURAL JOIN follow
    return render_template('showPosts.html', posts=data, tags=tags)

@app.route("/manageRequests", methods=['GET','POST'])
def manageRequests():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    user = session['username'].lower()
    cursor = connection.cursor()
    query = 'SELECT * FROM follow WHERE followeeUsername=%s AND reqResponded=0'
    cursor.execute(query, user)
    followReq = cursor.fetchall()

    query = 'SELECT * FROM tag NATURAL JOIN photo WHERE username=%s AND reqResponded=0'
    cursor.execute(query, user)
    tagReq = cursor.fetchall()

    query = 'SELECT * FROM belong WHERE username=%s AND reqResponded=0'
    cursor.execute(query, user)
    groupReq = cursor.fetchall()

    cursor.close()


    if request.method=='POST':
        faccept = request.form.getlist('faccept')
        taccept = request.form.getlist('taccept')
        gaccept = request.form.getlist('gaccept')
        freject=request.form.getlist('freject')
        treject = request.form.getlist('treject')
        greject = request.form.getlist('greject')

        faquery = 'UPDATE follow SET acceptedFollow=1, reqResponded=1 WHERE followerUsername=%s AND followeeUsername=%s'
        taquery = 'UPDATE tag SET acceptedTag=1, reqResponded=1 WHERE username=%s AND photoID=%s'
        gaquery = 'UPDATE belong SET acceptedReq=1, reqResponded=1 WHERE username=%s AND groupName=%s'
        frquery = 'UPDATE follow SET acceptedFollow=0, reqResponded=1 WHERE followerUsername=%s AND followeeUsername=%s'
        trquery = 'UPDATE tag SET acceptedTag=0, reqResponded=1 WHERE username=%s AND photoID=%s'
        grquery = 'UPDATE belong SET acceptedReq=0, reqResponded=1 WHERE username=%s AND groupName=%s'

        cursor=connection.cursor()
        for row in faccept:
            items=row.split('-')
            cursor.execute(faquery, (items[1],items[0]))
            connection.commit()

        for row in freject:
            items=row.split('-')
            cursor.execute(frquery, (items[1],items[0]))
            connection.commit()

        for row in taccept:
            items=row.split('-')
            cursor.execute(taquery, (items[0],int(items[1])))
            connection.commit()

        for row in treject:
            items=row.split('-')
            cursor.execute(trquery, (items[0],int(items[1])))
            connection.commit()

        for row in gaccept:
            items=row.split('-')
            cursor.execute(gaquery, (items[1],items[0]))
            connection.commit()

        for row in greject:
            items=row.split('-')
            cursor.execute(grquery, (items[1],items[0]))
            connection.commit()


        cursor.close()
        flash('Requests have been updated')
        return home()


    return render_template('manageRequests.html', followReq=followReq, tagReq=tagReq, groupReq=groupReq)

@app.route("/follow", methods=['GET','POST'])
def follow():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)


    if request.method=='POST':
        user = session["username"].lower()
        followee = request.form['followee'].lower()
        q = "SELECT * FROM follow WHERE followerUsername = %s"
        cursor = connection.cursor()
        cursor.execute(q, (user))
        check = cursor.fetchone()
        cursor.close()

        if followee==user:
            flash("Can't follow yourself")
            return home()

        if check:
            flash("Already follow")
            return home()

        q="INSERT INTO follow(followeeUsername, followerUsername, acceptedFollow, reqResponded) VALUES (%s, %s, %s, %s)"
        cursor = connection.cursor()
        cursor.execute(q, (followee, user, 0, 0))
        connection.commit()
        cursor.close()

        #note = "Group has been created."
        flash('Request has been sent')
        return home()

    return render_template('follow.html')

@app.route("/searchPoster", methods=['GET','POST'])
def searchPoster():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    query='SELECT photoID, timestamp, caption, photoOwner, filePath FROM photo WHERE (photoOwner=%s ' \
    'OR photoID IN (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.groupName=%s AND ' \
    'belong.acceptedReq=1) OR photoID IN (SELECT photoID FROM follow WHERE follow.followeeUsername=%s and follow.acceptedFollow=1)) AND photoOwner=%s'

    cursor=connection.cursor()
    tagquery='SELECT * FROM tag'
    cursor.execute(tagquery)
    tags=cursor.fetchall()
    cursor.close()

    if request.method=='POST':
        user = session["username"].lower()
        poster=request.form['poster'].lower()
        cursor = connection.cursor()
        cursor.execute(query, (user, user, user, poster))
        posts=cursor.fetchall()
        cursor.close()
        return render_template('showPosts.html', posts=posts, tags=tags)

    return render_template('searchPoster.html')

@app.route("/searchTag", methods=['GET', 'POST'])
def searchTag():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    query='SELECT photoID, timestamp, caption, photoOwner, filePath FROM photo NATURAL JOIN tag WHERE (photoOwner=%s ' \
    'OR photoID IN (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.groupName=%s AND ' \
    'belong.acceptedReq=1) OR photoID IN (SELECT photoID FROM follow WHERE follow.followeeUsername=%s and follow.acceptedFollow=1)) AND tag.username=%s'

    cursor=connection.cursor()
    tagquery='SELECT * FROM tag'
    cursor.execute(tagquery)
    tags=cursor.fetchall()
    cursor.close()

    if request.method=='POST':
        user = session["username"].lower()
        tagee=request.form['tag'].lower()
        cursor = connection.cursor()
        cursor.execute(query, (user, user, user, tagee))
        posts=cursor.fetchall()
        cursor.close()
        return render_template('showPosts.html', posts=posts, tags=tags)

    return render_template('searchTag.html')


@app.route("/tag", methods=['GET', 'POST'])
def tag():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    user = session["username"].lower()
    query = 'SELECT photoID, timestamp, caption, photoOwner, filePath FROM photo WHERE photoOwner=%s ' \
            'OR photoID IN (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.groupName=%s AND ' \
            'belong.acceptedReq=1) OR photoID IN (SELECT photoID FROM follow WHERE follow.followeeUsername=%s and follow.acceptedFollow=1)'
    cursor=connection.cursor()
    cursor.execute(query,(user,user,user))
    posts=cursor.fetchall()
    cursor.close()

    if request.method == 'POST':
        friend=request.form['friend'].lower()
        images = request.form.getlist('tag')

        # query for all images viewable
        cursor = connection.cursor()
        check = 'SELECT photoID, timestamp, caption, photoOwner, filePath FROM photo WHERE photoOwner=%s ' \
            'OR photoID IN (SELECT photoID FROM share NATURAL JOIN belong WHERE belong.groupName=%s AND ' \
            'belong.acceptedReq=1) OR photoID IN (SELECT photoID FROM follow WHERE follow.followeeUsername=%s and follow.acceptedFollow=1) AND photoID=%s'

        check2q='SELECT * FROM tag WHERE photoID=%s AND username=%s' \
               ''
        for row in images:
            cursor.execute(check, (friend, friend, friend,row))
            check=cursor.fetchone()

            if not check:
                message = "Error: Photo(s) not viewable by tagged user"
                return render_template('tag.html', posts=posts, message=message)

            cursor.execute(check2q,(row,friend))
            check2=cursor.fetchone()
            if check2:
                message = "Friend already tagged"
                return render_template('tag.html', posts=posts, message=message)

            insert = 'INSERT INTO tag(username, photoID, acceptedTag, reqResponded) VALUES(%s, %s, %s,%s)'
            cursor.execute(insert,(friend,row,0,0))
            connection.commit()
            cursor.close()
            message="Friends have been tagged"
            return render_template('tag.html', posts=posts, message=message)

        cursor.close()
    return render_template("tag.html",posts=posts)


@app.route("/unfollow", methods=['GET', 'POST'])
def unfollow():
    if 'username' not in session:
        error = "Please log in to continue"
        return render_template('index.html', error=error)

    if request.method=='POST':
        user = session["username"].lower()
        unfollowee=request.form["username"].lower()
        cursor=connection.cursor()
        q='SELECT * FROM follow WHERE followeeUsername=%s AND followerUsername-%s'
        cursor.execute(q,(unfollowee, user))
        check=cursor.fetchone()
        cursor.close()
        if not check:
            flash('You do not follow this user')
            return home()

        update='DELETE FROM follow WHERE followeeUsername=%s and followerUsername=%s'
        cursor=connection.cursor()
        cursor.execute(update,(unfollowee,user))
        connection.commit()
        cursor.close()
        flash('You have unfollowed the user')
        return home()

    return render_template("unfollow.html")

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.debug=True

    app.run()
