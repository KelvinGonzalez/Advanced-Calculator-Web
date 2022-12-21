from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from .models import User
from . import db
from flask_login import login_user, login_required, logout_user, current_user
from pickle import dumps, loads
from pyperclip import copy
from .calculator import *
from math import *
from datetime import datetime

views = Blueprint('views', __name__)


def get_shared_objects():
    objects = []
    for user in User.query.all():
        for object in user.objects.values():
            if object.shared_time is not None:
                objects.append([user, object])
    return objects


def get_is_saved(user_id, object_name):
    for shared_object in current_user.shared_objects:
        if shared_object[0] == user_id and shared_object[1] == object_name:
            return True
    return False


def get_shared_object_popularity(user_id, object_name):
    count = 0
    for user in User.query.all():
        if [user_id, object_name] in user.shared_objects:
            count += 1
    return count


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == "POST":
        if request.form.get("var"):
            if current_user.variables.get(request.form.get("var")) is not None:
                current_user.variables.pop(request.form.get("var"))

        if request.form.get('expression') or request.form.get('def_var') or request.form.get('def_funct') or request.form.get('def_obj'):
            if request.form.get('expression'):
                prompt = request.form.get('expression')
            elif request.form.get('def_var'):
                prompt = "var " + request.form.get('def_var')
            elif request.form.get('def_funct'):
                prompt = "funct " + request.form.get('def_funct')
            elif request.form.get('def_obj'):
                prompt = "obj " + request.form.get('def_obj')

            if prompt.startswith("var "):
                data = prompt[len("var "):].split("=")
                if IsValidName(data[0].strip()):
                    if IsUniqueName(data[0].strip(), current_user.variables):
                        try:
                            value = eval(ParsePrompt(data[1].strip()))
                            if type(value) == Function or type(value) == Object:
                                pass
                            current_user.variables[data[0].strip()] = value
                            current_user.results.insert(0, f"Variable {data[0].strip()} created with value {str(value)}")
                            if len(current_user.results) > 25:
                                current_user.results.pop()
                        except:
                            pass

            elif prompt.startswith("funct "):
                name = prompt[len("funct "):prompt.find("(")].strip()
                if IsValidName(name):
                    if IsUniqueName(name, current_user.functions):
                        parameters = [x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                        if "" in parameters:
                            parameters.remove("")
                        value = prompt[prompt.find("=")+1:].strip()
                        current_user.functions[name] = Function(value, parameters)
                        current_user.results.insert(0, f"Function {name} created with value {value}")
                        if len(current_user.results) > 25:
                            current_user.results.pop()

            elif prompt.startswith("obj "):
                name = prompt[len("obj "):prompt.find("(")].strip()
                if IsValidName(name):
                    if IsUniqueName(name, current_user.objects):
                        attributes = [x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                        if "" in attributes:
                            attributes.remove("")
                        current_user.objects[name] = Object(name, attributes)
                        current_user.results.insert(0, f"Object {name} created as {str(current_user.objects[name])}")
                        if len(current_user.results) > 25:
                            current_user.results.pop()

            elif prompt == "clear":
                current_user.results.clear()

            else:
                try:
                    evaluated_expression = eval(ParsePrompt(prompt))
                    current_user.results.insert(0, f"{prompt} = {evaluated_expression}")
                    if len(current_user.results) > 25:
                        current_user.results.pop()
                    copy(repr(evaluated_expression))
                except:
                    pass

    db.session.commit()
    return render_template("home.html", user=current_user, loads=loads, dumps=dumps, saved_objects=get_saved_objects())


@views.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user:
            if user.password == password:
                login_user(user, remember=True)
                return redirect(url_for("views.home"))
    
    return render_template("login.html", user=current_user)


@views.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        user = User.query.filter_by(username=username).first()
        if not user and len(username) > 0 and len(password) > 0 and password == confirm_password:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            return redirect(url_for("views.home"))

    return render_template("sign_up.html", user=current_user)


@views.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('views.login'))


@views.route('/delete-funct', methods=['POST'])
@login_required
def delete_funct():
    temp = request.form.get('funct')
    if temp:
        #print(f"Deleted {temp}")
        if current_user.functions.get(temp) is not None:
            current_user.functions.pop(temp)
            db.session.commit()
    return redirect(url_for('views.home'))


def remove_object(object_name):
    for var in list(current_user.variables.keys()):
        if type(current_user.variables[var]) == Instance and current_user.variables[var].object == object_name:
            current_user.variables.pop(var)
    for obj in current_user.objects.keys():
        object = current_user.objects[obj]
        for svar in list(object.static_variables.keys()):
            if type(object.static_variables[svar]) == Instance and object.static_variables[svar].object == object_name:
                object.static_variables.pop(svar)
        current_user.objects[obj] = object
    current_user.objects.pop(object_name)
    db.session.commit()


def remove_shared_object(user_id, object_name):
    for user in User.query.all():
        if [user_id, object_name] in user.shared_objects:
            for var in list(user.variables.keys()):
                if type(user.variables[var]) == Instance and user.variables[var].object == object_name:
                    user.variables.pop(var)
            for obj in user.objects.keys():
                object = user.objects[obj]
                for svar in list(object.static_variables.keys()):
                    if type(object.static_variables[svar]) == Instance and object.static_variables[svar].object == object_name:
                        object.static_variables.pop(svar)
                user.objects[obj] = object
            user.shared_objects.remove([user_id, object_name])
    db.session.commit()


def remove_saved_object(user_id, object_name):
    for var in list(current_user.variables.keys()):
        if type(current_user.variables[var]) == Instance and current_user.variables[var].object == object_name:
            current_user.variables.pop(var)
    for obj in current_user.objects.keys():
        object = current_user.objects[obj]
        for svar in list(object.static_variables.keys()):
            if type(object.static_variables[svar]) == Instance and object.static_variables[svar].object == object_name:
                object.static_variables.pop(svar)
        current_user.objects[obj] = object
    current_user.shared_objects.remove([user_id, object_name])
    db.session.commit()


@views.route('/object', methods=['GET', 'POST'])
@login_required
def object():
    if request.method == "GET":
        object = list(current_user.objects.values())[0]
        saved = True
        user_id = -1

    elif request.method == "POST":
        user_id = int(request.form.get('user_id')) if request.form.get('user_id') else -1
        if user_id == -1:
            object = current_user.objects.get(request.form.get('obj'))
        else:
            object = User.query.get(user_id).objects.get(request.form.get('obj'))
        saved = True if request.form.get('saved') and request.form.get('saved') == 'true' else False

        collapsed = request.form.get('collapsed')
        if collapsed:
            current_user.collapsed[int(collapsed)] = not current_user.collapsed[int(collapsed)]

        delete_var = request.form.get('delete_var')
        if delete_var:
            object.variables.remove(delete_var)

        delete_funct = request.form.get('delete_funct')
        if delete_funct:
            object.functions.pop(delete_funct)

        delete_staticvar = request.form.get('delete_staticvar')
        if delete_staticvar:
            object.static_variables.pop(delete_staticvar)

        delete_staticfunct = request.form.get('delete_staticfunct')
        if delete_staticfunct:
            object.static_functions.pop(delete_staticfunct)

        if request.form.get('share'):
            if object.shared_time is None:
                object.shared_time = datetime.now()
            else:
                remove_shared_object(current_user.id, object.name)
                object.shared_time = None

        if request.form.get('delete'):
            remove_object(object.name)
            remove_shared_object(current_user.id, object.name)
            return redirect(url_for("views.home"))

        if request.form.get('unsave'):
            remove_saved_object(int(request.form.get('user_id')), request.form.get('obj'))
            return redirect(url_for("views.home"))

        if request.form.get("def_obj"):
            prompt = request.form.get("def_obj")
            name = prompt[:prompt.find("(")].strip()
            if IsValidName(name):
                if IsUniqueName(name, current_user.objects):
                    attributes = [x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                    if "" in attributes:
                        attributes.remove("")
                    current_user.objects[name] = Object(name, attributes)
                    current_user.results.insert(0, f"Object {name} created as {str(current_user.objects[name])}")
                    if len(current_user.results) > 25:
                        current_user.results.pop()

        if request.form.get('expression') or request.form.get('def_var') or request.form.get('def_funct') or request.form.get('def_staticvar') or request.form.get('def_staticfunct'):
            if request.form.get('expression'):
                prompt = request.form.get('expression')
            elif request.form.get('def_var'):
                prompt = "var " + request.form.get('def_var')
                print("Var")
            elif request.form.get('def_funct'):
                prompt = "funct " + request.form.get('def_funct')
                print("Funct")
            elif request.form.get('def_staticvar'):
                prompt = "staticvar " + request.form.get('def_staticvar')
                print("StaticVar")
            elif request.form.get('def_staticfunct'):
                prompt = "staticfunct " + request.form.get('def_staticfunct')
                print("StaticFunct")

            if prompt:
                if prompt.startswith('var '):
                    variables = [x.strip() for x in prompt[len("var "):].split(",")]
                    for variable in variables:
                        if object:
                            if IsValidName(variable) and IsUniqueNameInObject(variable, object.name):
                                object.variables.append(variable)
                                #print(f"Variable {variable} added to object {name}")

                elif prompt.startswith('funct '):
                    if object:
                        function = prompt[len("funct "):prompt.find("(")].strip()
                        if IsValidName(function) and IsUniqueNameInObject(function, object.name, "functions"):
                            parameters = ["self"]+[x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                            if "" in parameters:
                                parameters.remove("")
                            value = prompt[prompt.find("=")+1:].strip()
                            object.functions[function] = Function(value, parameters)
                            #print(f"Function {function} added to object {object.name} with value {value}")

                elif prompt.startswith('staticvar '):
                    if object:
                        variable = prompt[len("staticvar "):prompt.find("=")].strip()
                        if IsValidName(variable) and IsUniqueNameInObject(variable, object.name, "static variables"):
                            try:
                                value = eval(ParsePrompt(prompt[prompt.find("=") + 1:].strip()))
                                object.static_variables[variable] = value
                                #print(f"Static variable {variable} with value {str(value)} added to object {name}")
                            except:
                                pass

                elif prompt.startswith('staticfunct '):
                    if object:
                        function = prompt[len("staticfunct "):prompt.find("(")].strip()
                        if IsValidName(function) and IsUniqueNameInObject(function, object.name, "static functions"):
                            parameters = [x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                            if "" in parameters:
                                parameters.remove("")
                            value = prompt[prompt.find("=")+1:].strip()
                            object.static_functions[function] = Function(value, parameters)
                            #print(f"Static function {function} added to object {object.name} with value {value}")

        if user_id == -1:
            current_user.objects[object.name] = object

        db.session.commit()

    return render_template("object.html", user=current_user, object=object, saved=saved, user_id=user_id, User=User, saved_objects=get_saved_objects())


@views.route('/edit-collapsed', methods=['POST'])
@login_required
def edit_collapsed():
    print("Tried to collapse")
    temp = request.form.get('collapsed')
    if temp:
        current_user.collapsed[int(temp)] = not current_user.collapsed[int(temp)]
        db.session.commit()
    return redirect(url_for('views.home'))


def obj_search(text):
    results = []
    for user in User.query.all():
        for object in user.objects.values():
            if object.shared_time is not None:
                for snippet in text.split(" "):
                    if snippet.lower() in object.name.lower():
                        results.append([user, object])
    return results


def sort_time(element):
    return element[1].shared_time

def sort_popular(element):
    return get_shared_object_popularity(element[0].id, element[1].name)



@views.route('/shared-objects', methods=['GET', 'POST'])
@login_required
def shared_objects():
    page = 0
    objects_per_page = 9

    if request.method == "GET":
        objects = get_shared_objects()
        objects.sort(key=sort_time, reverse=True)
        search_obj = ""
        sort = "newest"

    elif request.method == "POST":
        if request.form.get('save'):
            save = True if request.form.get('save') == 'true' else False
            if save:
                current_user.shared_objects.append([int(request.form.get('user_id')), request.form.get('obj')])
            else:
                remove_saved_object(int(request.form.get('user_id')), request.form.get('obj'))

        if request.form.get("unshare"):
            object = current_user.objects.get(request.form.get("unshare"))
            remove_shared_object(current_user.id, object.name)
            object.shared_time = None
            current_user.objects[object.name] = object

        collapsed = request.form.get('collapsed')
        if collapsed:
            current_user.collapsed[int(collapsed)] = not current_user.collapsed[int(collapsed)]

        if request.form.get("def_obj"):
            prompt = request.form.get("def_obj")
            name = prompt[:prompt.find("(")].strip()
            if IsValidName(name):
                if IsUniqueName(name, current_user.objects):
                    attributes = [x.strip() for x in prompt[prompt.find("(")+1:FindClosingParenthesis(prompt, prompt.find("("))].split(",")]
                    if "" in attributes:
                        attributes.remove("")
                    current_user.objects[name] = Object(name, attributes)
                    current_user.results.insert(0, f"Object {name} created as {str(current_user.objects[name])}")
                    if len(current_user.results) > 25:
                        current_user.results.pop()

        search_obj = request.form.get("search_obj")
        objects = obj_search(search_obj)
        sort = request.form.get("sort")
        if sort == "newest":
            objects.sort(key=sort_time, reverse=True)
        elif sort == "popular":
            objects.sort(key=sort_popular, reverse=True)
        elif sort == "oldest":
            objects.sort(key=sort_time, reverse=False)

        if request.form.get("page"):
            page = int(request.form.get("page"))
            print(page)

        db.session.commit()

    return render_template("shared_objects.html", user=current_user, objects=objects, get_is_saved=get_is_saved, get_shared_object_popularity=get_shared_object_popularity, search_obj=search_obj, sort=sort, saved_objects=get_saved_objects(), page=page, objects_per_page=objects_per_page, ceil=ceil)

@views.route('/info', methods=['GET'])
def info():
    return render_template("info.html", user=current_user)
