import calendar
import json
import locale
import os
import pytz

from datetime import datetime, date, timedelta, time
from django.db.models import Min, Max, Sum
from django.utils import timezone

from diners.models import Diner, AccessLog, SatisfactionRating, ElementToEvaluate
from kitchen.models import ProcessedProduct, Warehouse
from products.models import Cartridge, PackageCartridge, Supply, ExtraIngredient, PackageCartridgeRecipe, \
    CartridgeRecipe
from sales.models import Ticket, TicketDetail, TicketExtraIngredient

DAYS_LIST = {
    'LUNES': 'Lunes',
    'MARTES': 'Martes',
    'MIÉRCOLES': 'Miércoles',
    'JUEVES': 'Jueves',
    'VIERNES': 'Viernes',
    'SÁBADO': 'Sábado',
    'DOMINGO': 'Domingo'
}


class Helper(object):
    def __init__(self):
        if os.name == 'posix':
            # Configuración locale en prod: https://askubuntu.com/questions/76013/how-do-i-add-locale-to-ubuntu-server
            locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')
        else:
            locale.setlocale(locale.LC_TIME, 'Spanish_Mexico')

        super(Helper, self).__init__()

    @staticmethod
    def naive_to_datetime(nd):
        if type(nd) == datetime:
            if nd.tzinfo is not None and nd.tzinfo.utcoffset(nd) is not None:  # Is Aware
                return nd
            else:  # Is Naive
                tz = pytz.timezone('America/Mexico_City')
                return tz.localize(nd)

        elif type(nd) == date:
            d = nd
            t = time(0, 0)
            new_date = datetime.combine(d, t)
            return pytz.timezone('America/Mexico_City').localize(new_date)

    def start_datetime(self, back_days):
        start_date = date.today() - timedelta(days=back_days)
        return self.naive_to_datetime(start_date)

    def end_datetime(self, back_days):
        end_date = self.start_datetime(back_days) + timedelta(days=1)
        return self.naive_to_datetime(end_date)

    @staticmethod
    def parse_to_datetime(dt):
        day = int(dt.split('-')[0])
        month = int(dt.split('-')[1])
        year = int(dt.split('-')[2])
        parse_date = date(year, month, day)
        return Helper.naive_to_datetime(parse_date)

    def are_equal_lists(self, list_1, list_2):
        """
         Checks if two lists are identical
        """
        list_1 = self.items_list_to_int(list_1)
        list_2 = self.items_list_to_int(list_2)

        list_1.sort()
        list_2.sort()

        if len(list_1) != len(list_2):
            return False
        else:
            for element in range(0, len(list_1)):
                if list_1[element] != list_2[element]:
                    return False

        return True

    @staticmethod
    def get_name_day(datetime_now):
        name_day = date(datetime_now.year, datetime_now.month, datetime_now.day)
        return DAYS_LIST[name_day.strftime('%A').upper()]

    @staticmethod
    def get_number_day(dt):
        days = {
            'Lunes': 0, 'Martes': 1, 'Miércoles': 2, 'Jueves': 3, 'Viernes': 4, 'Sábado': 5, 'Domingo': 6,
        }
        return days[Helper.get_name_day(dt)]

    @staticmethod
    def get_week_number(dt):
        return dt.isocalendar()[1]

    @staticmethod
    def items_list_to_int(list_to_cast):
        """
        Evaluates each of the elements of the list received and casts them to integers
        """
        cast_list = []
        for item in range(0, len(list_to_cast)):
            cast_list.append(int(list_to_cast[item]))

        return cast_list


def create_calendar_list(dt, max_dt):
    """
    Permite obtener una lista de fechas de cada semana a partir de una fecha especificada
    :type max_dt: date
    :type dt: date
    :return list
    """
    dow_lst = []

    for mont in range(1, 13):
        while dt.month == mont:
            if dt > max_dt:
                return dow_lst
            dt_week = dt.strftime('%W')
            dt_initial = dt.strftime('%d %b %Y')
            dt_initial_f = dt.strftime('%d-%m-%Y')
            dt_final = (dt + timedelta(days=6)).strftime('%d %b %Y')
            dt_final_f = (dt + timedelta(days=6)).strftime('%d-%m-%Y')
            dow_lst.append('Sem %s: %s - %s | %s,%s' % (dt_week, dt_initial, dt_final, dt_initial_f, dt_final_f))
            dt = dt + timedelta(days=7)

    return dow_lst


def week_finder_from_year(year: int, max_dt: date = None):
    """ Regresa todas las semanas de un año en específico
    :type year: int
    :type max_dt: date
    :return list
    """
    month = calendar.January
    dt = date(year, month, 1)

    if max_dt is None:
        max_dt = date(year, 12, 31)

    while dt.weekday() != calendar.MONDAY:
        dt = dt + timedelta(days=1)

    return create_calendar_list(dt, max_dt)


class SalesHelper(object):
    def __init__(self):
        self.__all_tickets = None
        self.__all_tickets_details = None
        self.__all_extra_ingredients = None
        super(SalesHelper, self).__init__()

    def set_all_tickets(self, start_date=None, end_date=None):
        if start_date is not None and end_date is not None:
            self.__all_tickets = Ticket.objects.select_related('seller'). \
                filter(created_at__range=[start_date, end_date])
        self.__all_tickets = Ticket.objects.select_related('seller').all()

    def set_all_tickets_details(self):
        self.__all_tickets_details = TicketDetail.objects. \
            select_related('ticket'). \
            select_related('cartridge'). \
            select_related('ticket__seller'). \
            select_related('package_cartridge'). \
            all()

    def set_all_extra_ingredients(self):
        self.__all_extra_ingredients = TicketExtraIngredient.objects. \
            select_related('ticket_detail'). \
            select_related('extra_ingredient'). \
            select_related('extra_ingredient__ingredient'). \
            all()

    @staticmethod
    def get_tickets(start_date=None, end_date=None):
        """        
        :rtype: django.db.models.query.QuerySet
        """
        if start_date is not None and end_date is not None:
            all_tickets = Ticket.objects.select_related('seller'). \
                filter(created_at__range=[start_date, end_date])
        else:
            all_tickets = Ticket.objects.select_related('seller').all()
        return all_tickets

    def get_all_tickets_details(self):
        """        
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_tickets_details is None:
            self.set_all_tickets_details()
        return self.__all_tickets_details

    @staticmethod
    def get_earnings(initial_date=None, final_date=None):

        earnings = TicketDetail.objects.all(). \
            select_related('ticket'). \
            filter(ticket__created_at__range=[initial_date, final_date]). \
            aggregate(total=Sum('price'))['total']

        if earnings is None:
            return '0.00'

        return earnings

    def get_all_extra_ingredients(self):
        """        
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_extra_ingredients is None:
            self.set_all_extra_ingredients()
        return self.__all_extra_ingredients

    def get_years_list(self):
        """
        Returns a list of all the years in which there have been sales
        """
        years_list = []

        for ticket in self.get_tickets():
            if ticket.created_at.year not in years_list:
                years_list.append(ticket.created_at.year)

        return years_list

    @staticmethod
    def get_dates_range_json():
        """
        Regresa un JSON con una lista de años
        La lista de años contiene listas de semanas, las cuales
            contienen la fecha de inicio y la fecha final
        """
        years_dict = {}

        # Obtiene el ticket más antiguo
        first_date = Ticket.objects.values('created_at').order_by('created_at').first()['created_at']

        years = list(range(first_date.year, datetime.today().year + 1))

        for year in years:
            years_dict[year] = week_finder_from_year(year, date.today())

        return years_dict

    @staticmethod
    def get_sales_list(start_dt=None, final_dt=None):
        """
        Obtiene una lista de objetos de ventas por día con los siguientes valores
            - Name
            - Date
            - Earnings
        """

        limit_day = start_dt + timedelta(days=1)
        total_days = (final_dt - start_dt).days
        week_sales_list = []
        count = 1

        while count <= total_days:
            day_object = {
                'date': str(start_dt.date().strftime('%d-%m-%Y')),
                'day_name': None,
                'earnings': None,
                'number_day': Helper.get_number_day(start_dt),
            }

            total_earnings = TicketDetail.objects.all(). \
                select_related('ticket'). \
                values('price'). \
                filter(ticket__created_at__range=[start_dt, limit_day]). \
                aggregate(total=Sum('price'))['total']

            if total_earnings is None:
                total_earnings = 0

            day_object['day_name'] = Helper.get_name_day(start_dt.date())
            day_object['earnings'] = total_earnings

            week_sales_list.append(day_object)

            # Reset data
            limit_day += timedelta(days=1)
            start_dt += timedelta(days=1)
            count += 1

        return week_sales_list

    @staticmethod
    def get_tickets_dict(initial_date=None, final_date=None):
        tickets_details = TicketDetail.objects.all(). \
            select_related('ticket'). \
            select_related('cartridge'). \
            select_related('ticket__seller'). \
            select_related('package_cartridge'). \
            filter(ticket__created_at__range=[initial_date, final_date]). \
            order_by('-ticket__created_at'). \
            values('ticket__id', 'ticket__order_number', 'ticket__seller__username', 'cartridge', 'cartridge__name',
                   'cartridge__price', 'package_cartridge', 'package_cartridge__name', 'price', 'quantity',
                   'ticket__created_at')

        tickets_details_dict = {}

        for ticket_detail in tickets_details:
            ticket_id = ticket_detail['ticket__id']

            # Si no se ha agregado el ticket, lo inicializa
            if ticket_id not in tickets_details_dict:
                order_number = ticket_detail['ticket__order_number']
                created_at = ticket_detail['ticket__created_at'].strftime('%B %d, %Y, %H:%M:%S %p')
                seller = ticket_detail['ticket__seller__username']

                tickets_details_dict[ticket_id] = {
                    'order_number': order_number,
                    'created_at': created_at,
                    'seller': seller,
                    'cartridges': [],
                    'packages': [],
                    'total': 0
                }

            if ticket_detail['cartridge'] is not None:
                cartridge = {
                    'name': ticket_detail['cartridge__name'],
                    'quantity': ticket_detail['quantity'],
                    'price': ticket_detail['price']
                }
                tickets_details_dict[ticket_id]['cartridges'].append(cartridge)
            elif ticket_detail['package_cartridge'] is not None:
                package = {
                    'name': ticket_detail['package_cartridge__name'],
                    'quantity': ticket_detail['quantity'],
                    'price': ticket_detail['price']
                }
                tickets_details_dict[ticket_id]['packages'].append(package)

            tickets_details_dict[ticket_id]['total'] += ticket_detail['price']

        return tickets_details_dict


class ProductsHelper(object):
    def __init__(self):
        super(ProductsHelper, self).__init__()
        self.__all_cartridges = None
        self.__all_packages_cartridges = None
        self.__all_supplies = None
        self.__all_extra_ingredients = None
        self.__all_cartridges_recipes = None
        self.__all_packages_cartridges_recipes = None

    def set_all_supplies(self):
        self.__all_supplies = Supply.objects.all()

    def set_all_cartridges(self):
        self.__all_cartridges = Cartridge.objects.all()

    def set_all_packages_cartridges(self):
        self.__all_packages_cartridges = PackageCartridge.objects.all()

    def set_all_cartridges_recipes(self):
        self.__all_cartridges_recipes = CartridgeRecipe.objects. \
            select_related('cartridge'). \
            select_related('supply'). \
            all()

    def set_all_package_cartridges_recipes(self):
        self.__all_packages_cartridges_recipes = PackageCartridgeRecipe.objects. \
            select_related('package_cartridge'). \
            select_related('cartridge'). \
            all()

    def set_all_extra_ingredients(self):
        self.__all_extra_ingredients = ExtraIngredient.objects. \
            select_related('ingredient'). \
            select_related('cartridge'). \
            all()

    def get_all_supplies(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_supplies is None:
            self.set_all_supplies()
        return self.__all_supplies

    def get_all_cartridges(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_cartridges is None:
            self.set_all_cartridges()
        return self.__all_cartridges

    def get_all_packages_cartridges(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_packages_cartridges is None:
            self.set_all_packages_cartridges()
        return self.__all_packages_cartridges

    def get_all_extra_ingredients(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_extra_ingredients is None:
            self.set_all_extra_ingredients()

        return self.__all_extra_ingredients

    def get_all_cartridges_recipes(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_cartridges_recipes is None:
            self.set_all_cartridges_recipes()

        return self.__all_cartridges_recipes

    def get_all_packages_cartridges_recipes(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_packages_cartridges_recipes is None:
            self.set_all_package_cartridges_recipes()

        return self.__all_packages_cartridges_recipes


class DinersHelper(object):
    def __init__(self):
        self.__all_diners = None
        self.__all_access_logs = None
        super(DinersHelper, self).__init__()

    def get_all_diners_logs_list(self, initial_date, final_date):
        helper = Helper()
        diners_logs_list = []

        diners_logs_objects = self.get_access_logs(initial_date, final_date)

        for diner_log in diners_logs_objects:
            diner_log_object = {
                'rfid': diner_log.RFID,
                'access': datetime.strftime(timezone.localtime(diner_log.access_to_room), "%B %d, %I, %H:%M:%S %p"),
                'number_day': helper.get_number_day(diner_log.access_to_room),
            }
            if diner_log.diner:
                diner_log_object['SAP'] = diner_log.diner.employee_number
                diner_log_object['name'] = diner_log.diner.name
            else:
                diner_log_object['SAP'] = ''
                diner_log_object['name'] = ''
            diners_logs_list.append(diner_log_object)
        return diners_logs_list

    @staticmethod
    def get_weeks_entries(branch_id, initial_dt, final_dt):
        """
        Gets the following properties for each week's day: Name, Date and Earnings
        """
        helper = Helper()
        limit_day = initial_dt + timedelta(days=1)
        weeks_list = []
        count = 1
        total_days = (final_dt - initial_dt).days

        while count <= total_days:
            diners_entries = AccessLog.objects.select_related('diner').order_by('-access_to_room'). \
                filter(branch_office=branch_id, access_to_room__range=[initial_dt, limit_day])
            day_object = {
                'date': str(timezone.localtime(initial_dt).date().strftime('%d-%m-%Y')),
                'day_name': helper.get_name_day(initial_dt.date()), 'entries': diners_entries.count(),
                'number_day': helper.get_number_day(initial_dt)}

            weeks_list.append(day_object)

            # Reset data
            limit_day += timedelta(days=1)
            initial_dt += timedelta(days=1)
            count += 1

        return weeks_list

    @staticmethod
    def get_access_logs(branch_id, initial_date=None, final_date=None):
        """
        Obtiene los registros de entradas de los comensales
        :rtype: django.db.models.query.QuerySet 
        """
        if initial_date is not None and final_date is not None:
            return AccessLog.objects.all(). \
                select_related('diner').order_by('-access_to_room'). \
                filter(access_to_room__range=(initial_date, final_date), branch_office=branch_id). \
                order_by('-access_to_room')
        else:
            return AccessLog.objects.all(). \
                select_related('diner').order_by('-access_to_room'). \
                filter(branch_office=branch_id). \
                order_by('-access_to_room')

    def get_access_logs_today(self):
        """
        :rtype: django.db.models.query.QuerySet 
        """
        if self.__all_access_logs is None:
            self.set_all_access_logs()
        helper = Helper()
        year = int(datetime.now().year)
        month = int(datetime.now().month)
        day = int(datetime.now().day)
        initial_date = helper.naive_to_datetime(date(year, month, day))
        final_date = helper.naive_to_datetime(initial_date + timedelta(days=1))
        return self.__all_access_logs. \
            filter(access_to_room__range=(initial_date, final_date)). \
            order_by('-access_to_room')

    def get_all_access_logs(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_access_logs is None:
            self.set_all_access_logs()
        return self.__all_access_logs

    def get_diners_per_hour_json(self):
        hours_list = []
        hours_to_count = 12
        start_hour = 5
        customer_count = 0
        logs = self.get_access_logs_today()

        while start_hour <= hours_to_count:
            hour = {'count': None, }
            for log in logs:
                log_datetime = str(log.access_to_room)
                log_date, log_time = log_datetime.split(" ")

                if log_time.startswith("0" + str(start_hour)):
                    customer_count += 1
                hour['count'] = customer_count

            hours_list.append(hour)
            customer_count = 0
            start_hour += 1

        return json.dumps(hours_list)

    def get_diners_actual_week(self, branch_office_id):
        if self.__all_access_logs is None:
            self.set_all_access_logs()
        helper = Helper()
        week_diners_list = []
        total_entries = 0
        days_to_count = helper.get_number_day(date.today())
        day_limit = days_to_count
        start_date_number = 0

        while start_date_number <= day_limit:
            day_object = {
                'date': str(helper.start_datetime(days_to_count).date().strftime('%d-%m-%Y')),
                'day_name': None,
                'entries': None,
                'number_day': helper.get_number_day(helper.start_datetime(days_to_count).date())
            }

            logs = self.__all_access_logs. \
                filter(access_to_room__range=[helper.start_datetime(days_to_count), helper.end_datetime(days_to_count)],
                       branch_office=branch_office_id)

            for _ in logs:
                total_entries += 1

            day_object['entries'] = str(total_entries)
            day_object['day_name'] = helper.get_name_day(helper.start_datetime(days_to_count).date())

            week_diners_list.append(day_object)

            # restarting counters
            days_to_count -= 1
            total_entries = 0
            start_date_number += 1

        return json.dumps(week_diners_list)

    def get_all_diners(self):
        """
        :rtype: django.db.models.query.QuerySet
        """
        if self.__all_diners is None:
            self.set_all_diners()
        return self.__all_diners

    def set_all_access_logs(self):
        """
        :rtype: django.db.models.query.QuerySet 
        """
        self.__all_access_logs = AccessLog.objects.select_related('diner').order_by('-access_to_room')

    def set_all_diners(self):
        self.__all_diners = Diner.objects.all()


class KitchenHelper(object):
    def __init__(self):
        super(KitchenHelper, self).__init__()
        self.__all_processed_products = None
        self.__all_warehouse = None

    def get_all_processed_products(self):
        """
        :rtype: django.db.models.query.QuerySet 
        """
        if self.__all_processed_products is None:
            self.set_all_processed_products()
        return self.__all_processed_products

    def get_all_warehouse(self):
        """
        :rtype: django.db.models.query.QuerySet 
        """
        if self.__all_warehouse is None:
            self.set_all_processed_products()
        return self.__all_warehouse

    def get_processed_products(self):
        processed_products_list = []
        sales_helper = SalesHelper()
        products_helper = ProductsHelper()

        for processed in self.get_all_processed_products().filter(status='PE')[:15]:
            processed_product_object = {
                'ticket_id': processed.ticket,
                'cartridges': [],
                'packages': [],
                'ticket_order': processed.ticket.order_number
            }

            for ticket_detail in sales_helper.get_all_tickets_details():
                if ticket_detail.ticket == processed.ticket:
                    if ticket_detail.cartridge:
                        cartridge = {
                            'quantity': ticket_detail.quantity,
                            'cartridge': ticket_detail.cartridge,
                        }
                        for extra_ingredient in sales_helper.get_all_extra_ingredients():
                            if extra_ingredient.ticket_detail == ticket_detail:
                                try:
                                    cartridge['name'] += extra_ingredient['extra_ingredient']
                                except Exception as e:
                                    cartridge['name'] = ticket_detail.cartridge.name
                                    cartridge['name'] += ' con ' + extra_ingredient.extra_ingredient.ingredient.name
                        processed_product_object['cartridges'].append(cartridge)

                    elif ticket_detail.package_cartridge:
                        package = {
                            'quantity': ticket_detail.quantity,
                            'package_recipe': []
                        }
                        package_recipe = products_helper.get_all_packages_cartridges_recipes().filter(
                            package_cartridge=ticket_detail.package_cartridge)

                        for recipe in package_recipe:
                            package['package_recipe'].append(recipe.cartridge)
                        processed_product_object['packages'].append(package)

            processed_products_list.append(processed_product_object)
        return processed_products_list

    def set_all_warehouse(self):
        self.__all_warehouse = Warehouse.objects.select_related('supply').all()

    def set_all_processed_products(self):
        self.__all_processed_products = ProcessedProduct.objects. \
            select_related('ticket'). \
            all()


class RatesHelper(object):
    def __init__(self):
        super(RatesHelper, self).__init__()

    @staticmethod
    def get_elements_to_evaluate(branch_office_pk):
        """
        :rtype: django.db.models.query.QuerySet
        """
        return ElementToEvaluate.objects.all().filter(branch_office=branch_office_pk)

    @staticmethod
    def get_dates_range_json():
        """
        Regresa un JSON con una lista de años
        La lista de años contiene listas de semanas, las cuales
            contienen la fecha de inicio y la fecha final
        """
        years_dict = {}

        # Obtiene el ticket más antiguo
        first_date = SatisfactionRating.objects.values('creation_date').order_by('creation_date').first()[
            'creation_date']
        years = list(range(first_date.year, datetime.today().year + 1))

        for year in years:
            years_dict[year] = week_finder_from_year(year, date.today())

        return years_dict

    @staticmethod
    def get_satisfaction_ratings(branch_office_id, initial_date: datetime = None, final_date: datetime = None):
        helper = Helper()
        initial_date = helper.naive_to_datetime(initial_date)
        final_date = helper.naive_to_datetime(final_date)
        if initial_date is not None and final_date is not None:
            return SatisfactionRating.objects.all(). \
                select_related('branch_office'). \
                prefetch_related('elements'). \
                filter(creation_date__range=[initial_date, final_date], branch_office=branch_office_id). \
                order_by('-creation_date')
        else:
            return SatisfactionRating.objects.all(). \
                select_related('branch_office'). \
                prefetch_related('elements'). \
                filter(branch_office=branch_office_id). \
                order_by('-creation_date')

    @staticmethod
    def get_info_rates_list(branch_office_id, initial_date: datetime = None, final_date: datetime = None):
        """
        Returns a list with all the rates data for te selected range
        :rtype: list
        """
        helper = Helper()
        suggestions_list = []

        while initial_date <= final_date:
            day_object = {
                'date': str(initial_date.strftime('%d-%m-%Y')),
                'day_name': None,
                'total_suggestions': None,
                'total_reactions': None,
                'number_day': helper.get_number_day(initial_date),
            }
            initial_dt = helper.naive_to_datetime(initial_date)
            final_dt = helper.naive_to_datetime(initial_date + timedelta(days=1))

            filtered_suggestions = SatisfactionRating.objects.all(). \
                select_related('branch_office'). \
                exclude(suggestion__isnull=True). \
                filter(creation_date__range=[initial_dt, final_dt],
                       branch_office=branch_office_id)

            filtered_reactions = SatisfactionRating.objects.all(). \
                select_related('branch_office'). \
                filter(creation_date__range=[initial_dt, final_dt],
                       branch_office=branch_office_id)

            day_object['total_suggestions'] = filtered_suggestions.count()
            day_object['total_reactions'] = filtered_reactions.count()
            day_object['day_name'] = helper.get_name_day(initial_date)
            suggestions_list.append(day_object)

            # restarting counters
            initial_date = initial_date + timedelta(days=1)

        return suggestions_list
