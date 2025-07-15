from django.db import models


class PageVisited(models.Model):
    """
    Model to track pages visited by users.
    """

    url = models.URLField(
        max_length=2000, verbose_name="Page URL", blank=True, null=True
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Visit Timestamp",
    )
