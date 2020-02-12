import logging

from django.contrib import admin
from django.db import models
from django.db.models.functions import Lower
from django.utils.html import format_html

from allianceauth.eveonline.models import EveCorporationInfo, EveAllianceInfo

from .app_settings import STRUCTURES_DEVELOPER_MODE
from .models import (
    EveCategory,
    EveGroup,
    EveType,
    EveRegion,
    EveConstellation,
    EveSolarSystem,
    EveMoon,
    EvePlanet,
    StructureTag,
    StructureService,
    Webhook,
    EveEntity,
    Owner,
    Notification,
    Structure
)
from . import tasks
from .utils import LoggerAddTag


logger = LoggerAddTag(logging.getLogger(__name__), __package__)


if STRUCTURES_DEVELOPER_MODE:
    @admin.register(EveConstellation)
    class EveConstellationAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveEntity)
    class EveEntityAdmin(admin.ModelAdmin):
        list_display = (
            'id',
            'name',
            'category',
        )
        list_filter = ('category',)
        list_display_links = None

    @admin.register(EveCategory)
    class EveCategoryAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveGroup)
    class EveGroupAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveMoon)
    class EveMoonAdmin(admin.ModelAdmin):
        pass

    @admin.register(EvePlanet)
    class EvePlanetAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveRegion)
    class EveRegionAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveSolarSystem)
    class EveSolarSystemAdmin(admin.ModelAdmin):
        pass

    @admin.register(EveType)
    class EveTypeAdmin(admin.ModelAdmin):
        pass


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'notification_id',
        'owner',
        'notification_type',
        'timestamp',
        'created',
        'last_updated',
        '_webhooks',
        'is_sent',
        'is_timer_added'
    )
    list_filter = (
        'owner',
        'notification_type',
        'is_sent'
    )
    ordering = ['notification_id', 'owner']

    def _webhooks(self, obj):
        names = [x.name for x in obj.owner.webhooks.all().order_by('name')]
        if names:
            return ', '.join(names)
        else:
            return None

    _webhooks.short_description = 'Webhooks'

    actions = (
        'mark_as_sent',
        'mark_as_unsent',
        'send_to_webhook',
        'process_for_timerboard'
    )

    def mark_as_sent(self, request, queryset):
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = True
            obj.save()
            notifications_count += 1

        self.message_user(
            request,
            '{} notifications marked as sent'.format(notifications_count)
        )

    mark_as_sent.short_description = "Mark selected notifications as sent"

    def mark_as_unsent(self, request, queryset):
        notifications_count = 0
        for obj in queryset:
            obj.is_sent = False
            obj.save()
            notifications_count += 1

        self.message_user(
            request,
            '{} notifications marked as unsent'.format(notifications_count)
        )

    mark_as_unsent.short_description = \
        "Mark selected notifications as unsent"

    def send_to_webhook(self, request, queryset):
        obj_pks = [obj.pk for obj in queryset]        
        tasks.send_notifications.delay(obj_pks)            

        self.message_user(
            request,
            'Initiated sending of {} notifications to '
            'configured webhooks'.format(len(obj_pks))
        )

    send_to_webhook.short_description = \
        "Send selected notifications to configured webhooks"

    def process_for_timerboard(self, request, queryset):
        notifications_count = 0
        for obj in queryset:
            if obj.process_for_timerboard():
                notifications_count += 1

        self.message_user(
            request,
            'Added timers from {} notifications to timerboard'.format(
                notifications_count
            )
        )

    process_for_timerboard.short_description = \
        "Process selected notifications for timerboard"

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False


class OwnerSyncStatusFilter(admin.SimpleListFilter):
    title = 'is sync ok'

    parameter_name = 'sync_status__exact'

    def lookups(self, request, model_admin):
        """List of values to allow admin to select"""
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        """Return the filtered queryset"""
        if self.value() == 'yes':
            return queryset.filter(
                structures_last_error=Owner.ERROR_NONE,
                notifications_last_error=Owner.ERROR_NONE,
                forwarding_last_error=Owner.ERROR_NONE
            )
        elif self.value() == 'no':
            return queryset.exclude(
                structures_last_error=Owner.ERROR_NONE,
                notifications_last_error=Owner.ERROR_NONE,
                forwarding_last_error=Owner.ERROR_NONE
            )
        else:
            return queryset


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_select_related = True
    list_display = (
        '_corporation',
        '_alliance',
        'character',
        '_webhooks',
        'is_active',
        '_is_sync_ok',
    )
    list_filter = (
        ('corporation__alliance', admin.RelatedOnlyFieldListFilter),
        'is_active',
        OwnerSyncStatusFilter,
    )
    ordering = ['corporation__corporation_name']
    fieldsets = (
        (None, {
            'fields': (
                'corporation',
                'character',
                'webhooks',
                'is_alliance_main',
                'is_included_in_service_status',
                'is_active',
            )
        }),
        ('Sync Status', {
            'classes': ('collapse',),
            'fields': (
                ('structures_last_sync', 'structures_last_error', ),
                ('notifications_last_sync', 'notifications_last_error', ),
                ('forwarding_last_sync', 'forwarding_last_error', ),
            )
        }),
    )

    def _corporation(self, obj):        
        return obj.corporation.corporation_name
    
    _corporation.admin_order_field = 'corporation__corporation_name'
        
    def _alliance(self, obj):
        if obj.corporation.alliance:
            return obj.corporation.alliance.alliance_name
        else:
            return None

    _alliance.admin_order_field = 'corporation__alliance__alliance_name'

    def _webhooks(self, obj):
        webhook_names = [x.name for x in obj.webhooks.all().order_by('name')]
        if webhook_names:
            return ', '.join(webhook_names)
        else:
            return None

    _webhooks.short_description = 'Webhooks'

    def _is_sync_ok(self, obj):
        return obj.notifications_last_error == Owner.ERROR_NONE \
            and obj.structures_last_error == Owner.ERROR_NONE \
            and obj.forwarding_last_error == Owner.ERROR_NONE

    _is_sync_ok.boolean = True

    def get_readonly_fields(self, request, obj=None):
        if obj:    # editing an existing object
            return self.readonly_fields + (
                'notifications_last_error',
                'notifications_last_sync',
                'structures_last_error',
                'structures_last_sync',
                'forwarding_last_sync',
                'forwarding_last_error',
            )
        return self.readonly_fields

    actions = (
        'update_structures',
        'fetch_notifications',
        'send_notifications'
    )

    def update_structures(self, request, queryset):
        for obj in queryset:
            tasks.update_structures_for_owner.delay(
                obj.pk,
                force_sync=True,
                user_pk=request.user.pk
            )
            text = 'Started updating structures for: {}. '.format(obj)
            text += 'You will receive a notification once it is completed.'

            self.message_user(
                request,
                text
            )

    update_structures.short_description = "Update structures from EVE server"

    def fetch_notifications(self, request, queryset):
        for obj in queryset:
            tasks.fetch_notifications_for_owner.delay(
                obj.pk,
                force_sync=True,
                user_pk=request.user.pk
            )
            text = 'Started fetching notifications for: {}. '.format(obj)
            text += 'You will receive a notification once it is completed.'

            self.message_user(
                request,
                text
            )

    fetch_notifications.short_description = \
        "Fetch notifications from EVE server"

    def send_notifications(self, request, queryset):
        for obj in queryset:
            tasks.send_new_notifications_for_owner.delay(
                obj.pk
            )
            self.message_user(
                request,
                'Started sending new notifications for: {}. '.format(obj)
            )

    send_notifications.short_description = "Send new notifications to Discord"

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False


@admin.register(StructureTag)
class StructureTagAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'description',
        'style',
        'is_default',
    )
    list_filter = (
        'is_default',
        'style',
    )
    ordering = ['name']


class StructureAdminInline(admin.TabularInline):
    model = StructureService

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_change_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def has_delete_permission(self, request, obj=None):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False


class OwnerCorporationsFilter(admin.SimpleListFilter):
    """Custom filter to filter on corporations from owners only"""
    title = 'owner corporation'
    parameter_name = 'owner_corporation_id__exact'

    def lookups(self, request, model_admin):
        qs = EveCorporationInfo.objects\
            .filter(owner__isnull=False)\
            .values('corporation_id', 'corporation_name')\
            .distinct()\
            .order_by(Lower('corporation_name'))
        return tuple(
            [(x['corporation_id'], x['corporation_name']) for x in qs]
        )

    def queryset(self, request, qs):
        if self.value() is None:
            return qs.all()
        else:
            return qs.filter(owner__corporation__corporation_id=self.value())


class OwnerAllianceFilter(admin.SimpleListFilter):
    """Custom filter to filter on alliances from owners only"""
    title = 'owner alliance'
    parameter_name = 'owner_alliance_id__exact'

    def lookups(self, request, model_admin):
        qs = EveAllianceInfo.objects\
            .filter(evecorporationinfo__owner__isnull=False)\
            .values('alliance_id', 'alliance_name')\
            .distinct()\
            .order_by(Lower('alliance_name'))
        return tuple(
            [(x['alliance_id'], x['alliance_name']) for x in qs]
        )

    def queryset(self, request, qs):
        if self.value() is None:
            return qs.all()
        else:        
            return qs\
                .filter(owner__corporation__alliance__alliance_id=self.value())
            

@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    show_full_result_count = True
    list_select_related = True
    search_fields = [
        'name',
        'owner__corporation__corporation_name',
        'eve_solar_system__name'
    ]
    ordering = ['name']
    list_display = (
        'name',
        '_owner',
        '_location',
        '_type',
        '_tags'
    )
    list_filter = (
        OwnerCorporationsFilter,
        OwnerAllianceFilter,
        ('eve_solar_system', admin.RelatedOnlyFieldListFilter),
        (
            'eve_solar_system__eve_constellation__eve_region',
            admin.RelatedOnlyFieldListFilter
        ),
        ('eve_type', admin.RelatedOnlyFieldListFilter),
        ('eve_type__eve_group', admin.RelatedOnlyFieldListFilter),
        (
            'eve_type__eve_group__eve_category',
            admin.RelatedOnlyFieldListFilter
        ),
        ('tags', admin.RelatedOnlyFieldListFilter),
    )

    actions = ('add_default_tags', 'remove_all_tags', )

    def _owner(self, obj):
        return format_html(
            '{}<br>{}',
            obj.owner.corporation,
            obj.owner.corporation.alliance
        )

    def _location(self, obj):
        if obj.eve_moon:
            location_name = obj.eve_moon.name
        elif obj.eve_planet:
            location_name = obj.eve_planet.name
        else:
            location_name = obj.eve_solar_system.name
        return format_html(
            '{}<br>{}',
            location_name,
            obj.eve_solar_system.eve_constellation.eve_region
        )

    def _type(self, obj):
        return format_html(
            '{}<br>{}',
            obj.eve_type,
            obj.eve_type.eve_group
        )

    def _tags(self, obj):
        tag_names = [x.name for x in obj.tags.all().order_by('name')]
        if tag_names:
            return tag_names
        else:
            return None

    _tags.short_description = 'Tags'

    def has_add_permission(self, request):
        if STRUCTURES_DEVELOPER_MODE:
            return True
        else:
            return False

    def add_default_tags(self, request, queryset):
        structure_count = 0
        tags = StructureTag.objects.filter(is_default=True)
        for obj in queryset:
            for tag in tags:
                obj.tags.add(tag)
            structure_count += 1

        self.message_user(
            request,
            'Added {:,} default tags to {:,} structures'.format(
                tags.count(),
                structure_count
            ))

    add_default_tags.short_description = \
        "Add default tags to selected structures"

    def remove_all_tags(self, request, queryset):
        structure_count = 0
        for obj in queryset:
            obj.tags.clear()
            structure_count += 1

        self.message_user(
            request,
            'Removed all tags from {:,} structures'.format(structure_count))

    remove_all_tags.short_description = \
        "Remove all tags from selected structures"

    if not STRUCTURES_DEVELOPER_MODE:
        readonly_fields = tuple([
            x.name for x in Structure._meta.get_fields()
            if isinstance(x, models.fields.Field)
            and x.name not in ['tags']
        ])

    fieldsets = (
        (None, {
            'fields': (
                'name', 'owner', 'eve_solar_system', 'eve_type', 'tags'
            )
        }),
        ('Status', {
            'classes': ('collapse',),
            'fields': (
                'state',
                ('state_timer_start', 'state_timer_end', ),
                'unanchors_at',
                'fuel_expires'
            )
        }),
        ('Reinforcement', {
            'classes': ('collapse',),
            'fields': (
                ('reinforce_hour', ),
                (
                    'next_reinforce_hour',
                    'next_reinforce_weekday',
                    'next_reinforce_apply'
                ),
            )
        }),
        ('Position', {
            'classes': ('collapse',),
            'fields': ('position_x', 'position_y', 'position_z')
        }),
        (None, {
            'fields': (
                ('id', 'last_updated', )
            )
        }),
    )
    inlines = (StructureAdminInline, )


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    ordering = ['name']
    list_display = ('name', 'webhook_type', 'is_active', 'is_default')
    list_filter = ('webhook_type', 'is_active')
    save_as = True
    actions = (
        'test_notification',
        'activate',
        'deactivate'
    )

    def test_notification(self, request, queryset):
        for obj in queryset:
            tasks.send_test_notifications_to_webhook.delay(
                obj.pk,
                user_pk=request.user.pk
            )
            self.message_user(
                request,
                'Initiated sending test notification to webhook "{}". '
                'You will receive a report on completion.'.format(obj)
            )

    test_notification.short_description = \
        "Send test notification to selected webhooks"

    def activate(self, request, queryset):
        for obj in queryset:
            obj.is_active = True
            obj.save()

            self.message_user(
                request,
                'You have activated profile "{}"'.format(obj)
            )

    activate.short_description = 'Activate selected profiles'

    def deactivate(self, request, queryset):
        for obj in queryset:
            obj.is_active = False
            obj.save()

            self.message_user(
                request,
                'You have de-activated profile "{}"'.format(obj)
            )

    deactivate.short_description = 'Deactivate selected profiles'
