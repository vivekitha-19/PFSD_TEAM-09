from django.shortcuts import render, redirect

users = {}

def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        users[email] = {
            "name": name,
            "password": password
        }

        return redirect("/login/")

    return render(request, "register.html")


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if email in users and users[email]["password"] == password:
            request.session["name"] = users[email]["name"]
            return redirect("/home/")

    return render(request, "login.html")


def home(request):
    name = request.session.get("name", "Farmer")
    return render(request, "index.html", {"name": name})


def logout_view(request):
    request.session.flush()
    return redirect("/")