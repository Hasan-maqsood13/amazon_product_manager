from django.contrib import admin
from core.models import *

# Register your models here.
admin.site.register(User)
admin.site.register(receipts)
admin.site.register(receipt_items)
admin.site.register(stickers)
admin.site.register(sticker_data)
admin.site.register(match_history)
admin.site.register(ASINs)
admin.site.register(MatchedProducts)

