# This file is part product_rivals_netrivals module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import urllib2
from xml.dom import minidom
from decimal import Decimal
from simpleeval import simple_eval
from trytond.config import config
from trytond.pool import Pool, PoolMeta
from trytond.tools import decistmt

__all__ = ['ProductAppRivals']
DIGITS = config.getint('product', 'price_decimal', default=4)


class ProductAppRivals:
    __name__ = 'product.app.rivals'
    __metaclass__ = PoolMeta

    @classmethod
    def get_app(cls):
        res = super(ProductAppRivals, cls).get_app()
        res.append(('netrivals', 'Netrivals'))
        return res

    def update_prices_netrivals(self):
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Rivals = pool.get('product.rivals')

        values = {}
        to_create = []
        to_write = []
        template_write = []

        usock = urllib2.urlopen(self.app_uri) 
        xmldoc = minidom.parse(usock)

        for e in xmldoc.getElementsByTagName('Product'):
            code = e.getElementsByTagName('MPN')[0].firstChild.data # code
            min_price = e.getElementsByTagName('RivalMinPrice')[0].firstChild.data
            max_price = e.getElementsByTagName('RivalMaxPrice')[0].firstChild.data
            rivals = {}
            for r in e.getElementsByTagName('Rivals')[0].getElementsByTagName('Rival'):
                rival_name = r.getElementsByTagName('Name')[0].firstChild.data
                rival_price = r.getElementsByTagName('Price')[0].firstChild.data
                rivals[rival_name] = rival_price
            values[code] = {
                'rivals': rivals,
                'min_price': Decimal(min_price),
                'max_price': Decimal(max_price),
                }

        codes = values.keys()
        products = Product.search([
            ('code', 'in', codes),
            ])

        for p in products:
            if p.code in values:
                rivals = values[p.code]['rivals']
                product_rivals = {}
                for n in p.rivals:
                    product_rivals[n.name] = n

                for rival in rivals:
                    if self.tax_included:
                        price_w_tax = Decimal(rivals[rival])
                        price = self.get_price_without_tax(p, price_w_tax)
                    else:
                        price = Decimal(rivals[rival])
                        price_w_tax = self.get_price_with_tax(p, price)
                    if rival in product_rivals: # write
                        to_write.extend(([product_rivals[rival]], {
                            'price': price,
                            'price_w_tax': price_w_tax,
                            }))
                    else: # create
                        to_create.append({
                            'product': p,
                            'name': rival,
                            'price': price,
                            'price_w_tax': price_w_tax,
                            })

                rival_prices = {}

                # min rivals price
                min_price = values[p.code]['min_price']
                if self.tax_included:
                    min_price = self.get_price_without_tax(p, min_price)
                if min_price:
                    if self.formula_min_price:
                        context = self.get_context_formula(p)
                        context['names']['min_price'] = min_price
                        if not simple_eval(decistmt(self.formula_min_price), **context):
                            min_price = None
                    if min_price:
                        if self.tax_included:
                            min_price = self.get_price_without_tax(p,
                                min_price)
                        rival_prices['list_price_min_rival'] = min_price

                # max rivals price
                max_price = values[p.code]['max_price']
                if self.tax_included:
                    max_price = self.get_price_without_tax(p, max_price)
                if max_price:
                    if self.formula_max_price:
                        context = self.get_context_formula(p)
                        context['names']['max_price'] = max_price
                        if not simple_eval(decistmt(self.formula_max_price), **context):
                            max_price = None
                    if max_price:
                        if self.tax_included:
                            max_price = self.get_price_without_tax(p,
                                max_price)
                        rival_prices['list_price_max_rival'] = max_price

                # min / max prices (rival prices)
                if rival_prices and p.validate_min_max_price(rival_prices):
                    template_write.extend(([p.template], rival_prices))

        if to_create:
            Rivals.create(to_create)
        if to_write:
            Rivals.write(*to_write)
        if template_write:
            Template.write(*template_write)
