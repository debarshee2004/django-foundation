from django.shortcuts import render

from visits.models import PageVisited


def home_page_view(request, *args, **kwargs):
    page_context = {
        "title": "Welcome to My Website",
        "content": "This is the home page of my website.",
    }

    path = request.path
    if path:
        PageVisited.objects.create(url=path)
    return render(request, "home.html", page_context)


def about_page_view(request, *args, **kwargs):
    page_context = {
        "title": "About Us",
        "content": "This page contains information about our website.",
    }

    path = request.path
    if path:
        PageVisited.objects.create(url=path)
    return render(request, "about.html", page_context)
