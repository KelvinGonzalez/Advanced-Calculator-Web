from flask_login import current_user
from math import *
from . import db
from .models import User


def FindClosingParenthesis(text, index, starter="(", ender=")"):
    if text[index] != starter:
        return -1
    memory = 1
    for i in range(index + 1, len(text)):
        if text[i] == starter:
            memory += 1
        elif text[i] == ender:
            memory -= 1
        if memory == 0:
            return i
    return -1


def IsValidChar(char):
    return char.isalnum() or char == "_"


def IsValidName(name):
    for c in name:
        if not IsValidChar(c):
            return False
    return True


def IsCorrectName(start, name, prompt):
    count = len(name)
    i = start-1
    while i >= 0 and (IsValidChar(prompt[i]) or prompt[i] == "."):
        count += 1
        i -= 1
    i = start + len(name)
    while i < len(prompt) and IsValidChar(prompt[i]):
        count += 1
        i += 1
    return len(name) == count


def get_saved_objects():
    objects = {}
    for shared_object in current_user.shared_objects:
        for user in User.query.all():
            if shared_object[0] == user.id:
                objects[shared_object[1]] = [shared_object[0], user.objects.get(shared_object[1])]
    return objects

def get_object(name):
    if current_user.objects.get(name):
        return current_user.objects.get(name)
    else:
        saved_objects = get_saved_objects()
        for so in saved_objects.keys():
            if so == name:
                return saved_objects[so][1]


def ParsePrompt(prompt):
    result_prompt = prompt
    for o in current_user.objects.keys():
        i = 0
        while i < len(result_prompt):
            if result_prompt[i:i+len(o)] == o and IsCorrectName(i, o, result_prompt):
                replacement_text = f"current_user.objects[\"{o}\"]"
                result_prompt = result_prompt[:i] + replacement_text + result_prompt[i+len(o):]
                i += len(replacement_text) - len(o)
            i += 1
    saved_objects = get_saved_objects()
    for so in saved_objects.keys():
        i = 0
        while i < len(result_prompt):
            if result_prompt[i:i+len(so)] == so and IsCorrectName(i, so, result_prompt):
                replacement_text = f"User.query.get({saved_objects[so][0]}).objects[\"{so}\"]"
                result_prompt = result_prompt[:i] + replacement_text + result_prompt[i+len(so):]
                i += len(replacement_text) - len(so)
            i += 1
    for f in current_user.functions.keys():
        i = 0
        while i < len(result_prompt):
            if result_prompt[i:i+len(f)] == f and IsCorrectName(i, f, result_prompt):
                replacement_text = f"current_user.functions[\"{f}\"]"
                result_prompt = result_prompt[:i] + replacement_text + result_prompt[i+len(f):]
                i += len(replacement_text) - len(f)
            i += 1
    for v in current_user.variables.keys():
        i = 0
        while i < len(result_prompt):
            if result_prompt[i:i+len(v)] == v and IsCorrectName(i, v, result_prompt):
                replacement_text = f"current_user.variables[\"{v}\"]"
                result_prompt = result_prompt[:i] + replacement_text + result_prompt[i+len(v):]
                i += len(replacement_text) - len(v)
            i += 1
    return result_prompt


def ParseFunctionParameters(function_text, parameters):
    result_function_text = function_text
    for i in range(len(parameters)):
        j = 0
        while j < len(result_function_text):
            if result_function_text[j:j+len(parameters[i])] == parameters[i] and IsCorrectName(j, parameters[i], result_function_text):
                replacement_text = f"args[{i}]"
                result_function_text = result_function_text[:j] + replacement_text + result_function_text[j+len(parameters[i]):]
                j += len(replacement_text) - len(parameters[i])
            j += 1
    return result_function_text


class Function:
    def __init__(self, funct, args=None):
        if args is None:
            args = []

        self.funct = funct
        self.args = args

    def __call__(self, *args):
        return eval(ParsePrompt(ParseFunctionParameters(self.funct, self.args)))

    def __repr__(self):
        return f"Function(\"{self.funct}\", {self.args})"

    def __str__(self):
        return f"f({', '.join(self.args)}) = {self.funct}"


class ObjectFunctionHelper:
    def __init__(self, object, function_name, function):
        self.object = object
        self.function_name = function_name
        self.function = function

    def __call__(self, *args):
        args_string = ", ".join([f"args[{i}]" for i in range(len(args))])
        return eval(f"self.object.do('{self.function_name}', {args_string})")

    def __repr__(self):
        return repr(self.function)

    def __str__(self):
        return str(self.function)


class Object:
    def __init__(self, name, variables=None, functions=None, static_variables=None, static_functions=None, shared_time=None):
        if variables is None:
            variables = []
        if functions is None:
            functions = {}
        if static_variables is None:
            static_variables = {}
        if static_functions is None:
            static_functions = {}

        self.name = name
        self.variables = variables
        self.functions = functions
        self.static_variables = static_variables
        self.static_functions = static_functions
        self.shared_time = shared_time

    def __call__(self, *args):
        if len(args) == len(self.variables):
            return Instance(self.name, list(args))
        elif len(args) < len(self.variables):
            return Instance(self.name, list(args) + [None for i in range(len(self.variables)-len(args))])
        else:
            return Instance(self.name, list(args)[:len(self.variables)])

    def __repr__(self):
        functions_copy = {}
        static_functions_copy = {}
        for key in self.functions.keys():
            functions_copy[key] = Function(self.functions[key].funct.replace('"', '\\"'), self.functions[key].args)
        for key in self.static_functions.keys():
            static_functions_copy[key] = Function(self.static_functions[key].funct.replace('"', '\\"'), self.static_functions[key].args)
        return f"Object(\"{self.name}\", {self.variables}, {functions_copy}, {self.static_variables}, {static_functions_copy})"

    def __str__(self):
        return f"{self.name}({', '.join(self.variables)})"

    def __getattr__(self, item):
        if item in self.static_variables.keys():
            return self.get(item)
        elif item in self.static_functions.keys():
            return ObjectFunctionHelper(self, item, self.static_functions[item])

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)

    def get(self, name):
        return self.static_variables.get(name)

    def do(self, name, *args):
        function = self.static_functions.get(name)
        if function is None:
            return None
        args_string = ", ".join([f"args[{i}]" for i in range(len(args))])
        return eval(f"function({args_string})")

    def API(self):
        api_variables = " -" + ", ".join(self.variables)
        api_functions = "\n".join([f" -{f}({', '.join(self.functions[f].args)}) = {self.functions[f].funct}" for f in self.functions.keys()])
        api_static_variables = "\n".join([f" -{v} = {self.static_variables[v]}" for v in self.static_variables.keys()])
        api_static_functions = "\n".join([f" -{f}({', '.join(self.static_functions[f].args)}) = {self.static_functions[f].funct}" for f in self.static_functions.keys()])
        return f"{self.name} API:" + (f"\nVariables:\n{api_variables}" if len(self.variables) > 0 else "") + (f"\nFunctions:\n{api_functions}" if len(self.functions) > 0 else "") + (f"\nStatic Variables:\n{api_static_variables}" if len(self.static_variables) > 0 else "") + (f"\nStatic Functions:\n{api_static_functions}" if len(self.static_functions) > 0 else "")

    def is_shared(self):
        return self.shared_time is not None


class Instance:
    def __init__(self, object, variables=None):
        if variables is None:
            variables = []

        self.object = object
        self.variables = variables

    def __getattr__(self, item):
        if item in get_object(self.object).variables:
            return self.get(item)
        elif item in get_object(self.object).functions.keys():
            return ObjectFunctionHelper(self, item, get_object(self.object).functions[item])

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)

    def get(self, name):
        for i in range(len(get_object(self.object).variables)):
            if get_object(self.object).variables[i] == name:
                return self.variables[i]
        return None

    def do(self, name, *args):
        function = get_object(self.object).functions.get(name)
        if function is None:
            return None
        args_string = ", ".join([f"args[{i}]" for i in range(len(args))])
        return eval(f"function(self, {args_string})")

    def __repr__(self):
        return f"Instance(\"{self.object}\", {self.variables})"

    def __str__(self):
        if get_object(self.object).functions.get("str") is None:
            return self.__repr__()
        return get_object(self.object).functions["str"](self)

    def __add__(self, other):
        if get_object(self.object).functions.get("add") is None:
            return None
        return get_object(self.object).functions["add"](self, other)

    def __sub__(self, other):
        if get_object(self.object).functions.get("sub") is None:
            return None
        return get_object(self.object).functions["sub"](self, other)

    def __mul__(self, other):
        if get_object(self.object).functions.get("mul") is None:
            return None
        return get_object(self.object).functions["mul"](self, other)

    def __truediv__(self, other):
        if get_object(self.object).functions.get("div") is None:
            return None
        return get_object(self.object).functions["div"](self, other)

    def __mod__(self, other):
        if get_object(self.object).functions.get("mod") is None:
            return None
        return get_object(self.object).functions["mod"](self, other)

    def __pow__(self, other):
        if get_object(self.object).functions.get("pow") is None:
            return None
        return get_object(self.object).functions["pow"](self, other)

    def __cmp__(self, other):
        if get_object(self.object).functions.get("cmp") is None:
            return None
        return get_object(self.object).functions["cmp"](self, other)

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __neg__(self):
        if get_object(self.object).functions.get("neg") is None:
            return None
        return get_object(self.object).functions["neg"](self)

    def __invert__(self):
        if get_object(self.object).functions.get("invert") is None:
            return None
        return get_object(self.object).functions["invert"](self)

    def __abs__(self):
        if get_object(self.object).functions.get("abs") is None:
            return None
        return get_object(self.object).functions["abs"](self)

    def __len__(self):
        if get_object(self.object).functions.get("len") is None:
            return None
        return get_object(self.object).functions["len"](self)

    def __call__(self, *args):
        if get_object(self.object).functions.get("call") is None:
            return None
        args_string = ", ".join([f"args[{i}]" for i in range(len(args))])
        return eval(f"self.do('call', {args_string})")


def IsUniqueName(name, ignore):
    if current_user.variables != ignore and name in current_user.variables.keys():
        return False
    if current_user.functions != ignore and name in current_user.functions.keys():
        return False
    if current_user.objects != ignore and name in current_user.objects.keys():
        return False
    return True


def IsUniqueNameInObject(name, object_name, ignore=None):
    object = current_user.objects[object_name]
    if ignore != "variables" and name in object.variables:
        return False
    if ignore != "functions" and name in object.functions.keys():
        return False
    if ignore != "static variables" and name in object.static_variables.keys():
        return False
    if ignore != "static functions" and name in object.static_functions.keys():
        return False
    return True