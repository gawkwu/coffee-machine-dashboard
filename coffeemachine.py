#!/usr/bin/env Python 3.8
# encoding=utf-8


from enum import Enum, auto


class Menu:
    class Choices(Enum):
        ESPRESSO = 'Espresso'
        LATTE = 'Latte'
        CAPPUCCINO = 'Cappuccino'

    def __init__(self):
        self.recipes = {
            self.Choices.ESPRESSO: self.get_recipe(250, 0, 16, 1),
            self.Choices.LATTE: self.get_recipe(350, 75, 20, 1),
            self.Choices.CAPPUCCINO: self.get_recipe(200, 100, 12, 1)
        }
        self.cost = {
            self.Choices.ESPRESSO: 4,
            self.Choices.LATTE: 7,
            self.Choices.CAPPUCCINO: 6 
        }

    def get_recipe(self, water, milk, beans, cups):
        return dict(water=water, milk=milk, beans=beans, cups=cups)


class CoffeeMachine:
    class Command(Enum):
        BUY = auto()
        FILL = auto()
        TAKE = auto()
        REMAINING = auto()
        EXIT = auto()
    
    supplies = dict()
    menu = Menu()
    clerk = 'Jack'

    def __init__(self, water=0, milk=0, beans=0, cups=0, money=0):
        self.supplies['water'] = water
        self.supplies['milk'] = milk
        self.supplies['beans'] = beans
        self.supplies['cups'] = cups
        self.supplies['money'] = money
        self.running = None
    
    def __repr__(self):
        return "CoffeeMachine(water={water}, milk={milk}, beans={beans}, cups={cups}, money={money})"\
            .format(**self.supplies)
   
    def get_shortage(self, choice):
        """ Return a list of shortage, if machine don't have enough supplies for 
        the choice. """
        recipe = self.menu.recipes[choice]
        items = list(recipe)
        shortage = [i for i in items if self.supplies[i] < recipe[i]]
        return shortage
    
    def get_user_command(self):
        """ Return a Command from user input. """
        choices = [f'{i.value}.{i.name.capitalize()}' for i in self.Command]
        choice_str = ', '.join(choices)
        selection = int(input(f"Enter a choice ({choice_str}): "))
        return self.Command(selection)

    def get_user_choice(self):
        """ Return a choice of menu from user input. """
        choices = [f'{i.value}.{i.name.capitalize()}' for i in self.menu.Choices]
        choice_str = ', '.join(choices)
        selection = int(input(f"Choose a flavor ({choice_str}): "))
        return self.menu.Choices(selection)

    def receive_money(self, choice):
        """ According to the choice, add money to supplies. """
        self.supplies['money'] += self.menu.cost[choice]
        return self.supplies['money']

    def consume_supplies(self, choice):
        """ According to the choice, reduce materials of supplies """
        recipe = self.menu.recipes[choice]
        items = list(recipe)
        for i in items:
            self.supplies[i] -= recipe[i]
        return self.supplies
   
    def replenish(self, pack):
        """ Add materials to machine supplies. """
        items = list(pack)
        for i in items:
            self.supplies[i] += pack[i]
        return self.supplies

    def reset_supplies(self, items=None):
        """Reset items of the machine supplies to 0."""
        if items is None:
            items = set(self.supplies)
        for i in items:
            if i in self.supplies:
                self.supplies[i] = 0
        return self.supplies
    
    def withdraw_money(self):
        """ Print number of given money, and reset money to 0. """
        self.reset_supplies(['money'])
        return self.supplies['money']

    def print_remaining(self):
        """ Print out the machine status. """
        print(
            "----- Coffee Machine Status -----\n",
            "Water".ljust(20), f"{str(self.supplies['water']).ljust(5)} ml\n",
            "Milk".ljust(20), f"{str(self.supplies['milk']).ljust(5)} ml\n",
            "Coffee beans".ljust(20), f"{str(self.supplies['beans']).ljust(5)} g\n",
            "Disposable cups".ljust(20), f"{str(self.supplies['cups']).ljust(5)} pc\n",
            "Money".ljust(20), f"{str(self.supplies['money']).ljust(5)} dollars\n"
        )
    
    def clerk_print(self, text):
        """ Don't mind, just for some humanity. """
        print(f"[Clerk] {self.clerk}: {text}")

    def _buy(self):
        while True:
            try:
                choice = self.get_user_choice()
            except ValueError:
                choices = list(self.menu.Choices)
                print(f"Please enter a value in [{choices[0].value}, {choices[-1].value}]")
                continue

            shortage = self.get_shortage(choice)
            shortage_str = ', '.join(shortage)
            if shortage:
                self.clerk_print(f"Sorry, not enough {shortage_str}!")
            else:
                self.clerk_print(f"It's {self.menu.cost[choice]} dollars.")
                self.receive_money(choice)
                print(f"You get a {choice.name.capitalize()}.")
                self.consume_supplies(choice)
            break
        
    
    def _fill(self):
        while True:
            try:
                pack = dict(
                    water=int(input("How many ml of Water do you want to add: ")),
                    milk=int(input("How many ml of Milk do you want to add: ")),
                    beans=int(input("How many grams of Coffee Beans do you want to add: ")),
                    cups=int(input("How many Disposable Cups do you want to add: "))
                )
            except:
                print('Please enter a number.')
                continue

            if all([pack[i] > 0 for i in pack]):
                self.replenish(pack)
                break
            else:
                print('Please enter a positive number.')
                continue

    def _take(self):
        print(f"You had take ${self.supplies['money']} from machine.")
        self.withdraw_money()

    def _remaining(self):
        self.print_remaining()

    def _exit(self):
        self.clerk_print("Thanks for using, have a nice day :)")
        self.running = False

    def run(self):
        """ Main process of the machine. """
        self.running = True
        print('Welcome to use Coffee Machine Simulator!')
        while self.running:
            action = self.get_user_command()
            if action == self.Command.BUY:
                self._buy()
            elif action == self.Command.FILL:
                self._fill()
            elif action == self.Command.TAKE:
                self._take()
            elif action == self.Command.REMAINING:
                self._remaining()
            elif action == self.Command.EXIT:
                self._exit()
