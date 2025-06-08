#!/usr/bin/env python3
"""
EGA Trader - A space trading game inspired by EGA Trek
Features dynamic AI traders that move goods and affect market prices
"""

import random
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math

class StationType(Enum):
    TRADING_POST = "Trading Post"
    RESEARCH_STATION = "Research Station"
    MINING_COLONY = "Mining Colony"
    MANUFACTURING_HUB = "Manufacturing Hub"

class CommodityType(Enum):
    FOOD = "Food"
    MINERALS = "Minerals"
    TECHNOLOGY = "Technology"
    MEDICINE = "Medicine"
    LUXURIES = "Luxuries"
    FUEL = "Fuel"

class ShipType(Enum):
    PLAYER = "Player Ship"
    TRADER = "AI Trader"
    FREIGHT = "AI Freighter"
    PIRATE = "Pirate"

class AIPersonality(Enum):
    CAUTIOUS = "Cautious"      # Conservative trading, avoids risk
    AGGRESSIVE = "Aggressive"  # Takes bigger risks, higher profit margins
    OPPORTUNIST = "Opportunist" # Quick to exploit market imbalances
    SPECIALIST = "Specialist"  # Focuses on specific commodities

@dataclass
class Position:
    quadrant_x: int
    quadrant_y: int
    sector_x: int
    sector_y: int
    
    def __str__(self):
        return f"Q{self.quadrant_x},{self.quadrant_y} S{self.sector_x},{self.sector_y}"
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate distance between two positions"""
        q_dist = abs(self.quadrant_x - other.quadrant_x) + abs(self.quadrant_y - other.quadrant_y)
        if q_dist == 0:  # Same quadrant
            return abs(self.sector_x - other.sector_x) + abs(self.sector_y - other.sector_y)
        return q_dist * 8  # Quadrant distance is much larger

@dataclass
class Market:
    commodities: Dict[CommodityType, float]  # commodity -> current price
    supply_demand: Dict[CommodityType, float]  # base multiplier for station type
    stock_levels: Dict[CommodityType, int]  # how much the station has in stock
    
    def adjust_price(self, commodity: CommodityType, quantity_change: int):
        """Adjust price based on supply/demand - positive change = more supply (lower price)"""
        current_stock = self.stock_levels[commodity]
        price_impact = -quantity_change / max(100, current_stock) * 0.1  # Max 10% change
        
        current_price = self.commodities[commodity]
        new_price = current_price * (1 + price_impact)
        
        # Keep prices reasonable
        base_price = self._get_base_price(commodity)
        min_price = base_price * 0.5
        max_price = base_price * 2.0
        
        self.commodities[commodity] = max(min_price, min(max_price, new_price))
        self.stock_levels[commodity] = max(0, current_stock + quantity_change)
    
    def _get_base_price(self, commodity: CommodityType) -> float:
        base_prices = {
            CommodityType.FOOD: 100,
            CommodityType.MINERALS: 150,
            CommodityType.TECHNOLOGY: 500,
            CommodityType.MEDICINE: 300,
            CommodityType.LUXURIES: 800,
            CommodityType.FUEL: 80
        }
        return base_prices[commodity]

@dataclass
class Station:
    name: str
    station_type: StationType
    position: Position
    market: Market

@dataclass
class Ship:
    name: str
    ship_type: ShipType
    position: Position
    energy: int
    max_energy: int
    cargo_hold: Dict[CommodityType, int]
    max_cargo: int
    credits: float
    warp_factor: float
    max_warp: float
    
    # Ship systems (0-100% efficiency)
    engines: int
    life_support: int
    cargo_bay: int
    trading_computer: int
    shields: int
    
    # AI behavior
    destination: Optional[Position] = None
    trade_route: List[Position] = None
    last_trade_time: float = 0.0
    personality: Optional[AIPersonality] = None
    preferred_commodities: List[CommodityType] = None
    risk_tolerance: float = 0.5  # 0.0 = very cautious, 1.0 = very risky
    patience: float = 0.5        # How long to wait for better prices
    
    def total_cargo(self) -> int:
        return sum(self.cargo_hold.values())
    
    def cargo_space_remaining(self) -> int:
        return self.max_cargo - self.total_cargo()

class AITrader:
    def __init__(self, ship: Ship, galaxy: 'Galaxy'):
        self.ship = ship
        self.galaxy = galaxy
        self.trade_memory: Dict[Tuple[int, int], Dict[CommodityType, Tuple[float, float]]] = {}  # Remember prices and timestamps
        self.market_analysis: Dict[CommodityType, float] = {}  # Predicted price trends
        self.profit_history: List[float] = []  # Track recent profits
        self.last_analysis_time: float = 0.0
        
    def update(self, game_time: float):
        """Update AI trader behavior based on personality"""
        # Update trade memory and market analysis
        self._update_trade_memory(game_time)
        
        # Analyze market trends periodically
        if game_time - self.last_analysis_time > 5.0:
            self._analyze_market_trends()
            self.last_analysis_time = game_time
        
        # If at a station, try to trade
        station = self._get_current_station()
        if station:
            self._trade_at_station(station, game_time)
        
        # Move towards profitable opportunities
        self._plan_movement(game_time)
        self._move_ship()
    
    def _update_trade_memory(self, game_time: float):
        """Remember prices at current location with timestamps"""
        station = self._get_current_station()
        if station:
            pos_key = (station.position.quadrant_x, station.position.quadrant_y)
            price_data = {}
            for commodity, price in station.market.commodities.items():
                price_data[commodity] = (price, game_time)
            self.trade_memory[pos_key] = price_data
    
    def _analyze_market_trends(self):
        """Analyze price trends to predict future movements"""
        for commodity in CommodityType:
            prices = []
            for pos_data in self.trade_memory.values():
                if commodity in pos_data:
                    price, timestamp = pos_data[commodity]
                    prices.append(price)
            
            if len(prices) >= 2:
                # Simple trend analysis - compare recent prices to older ones
                recent_avg = sum(prices[-3:]) / len(prices[-3:]) if len(prices) >= 3 else prices[-1]
                older_avg = sum(prices[:-3]) / len(prices[:-3]) if len(prices) > 3 else prices[0]
                trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
                self.market_analysis[commodity] = trend
    
    def _get_current_station(self) -> Optional[Station]:
        """Check if ship is at a station"""
        for station in self.galaxy.stations:
            if (station.position.quadrant_x == self.ship.position.quadrant_x and
                station.position.quadrant_y == self.ship.position.quadrant_y and
                station.position.sector_x == self.ship.position.sector_x and
                station.position.sector_y == self.ship.position.sector_y):
                return station
        return None
    
    def _should_sell_commodity(self, commodity: CommodityType, station: Station, game_time: float) -> bool:
        """Decide whether to sell based on personality and market conditions"""
        sell_price = station.market.commodities[commodity]
        base_price = station.market._get_base_price(commodity)
        
        # Base profit threshold varies by personality
        if self.ship.personality == AIPersonality.CAUTIOUS:
            min_profit_margin = 0.05  # 5% profit minimum
        elif self.ship.personality == AIPersonality.AGGRESSIVE:
            min_profit_margin = 0.15  # 15% profit minimum
        elif self.ship.personality == AIPersonality.OPPORTUNIST:
            min_profit_margin = 0.08  # 8% profit minimum
        else:  # SPECIALIST
            if commodity in self.ship.preferred_commodities:
                min_profit_margin = 0.12  # Higher margin for specialty
            else:
                min_profit_margin = 0.03  # Lower margin for non-specialty
        
        profit_margin = (sell_price - base_price) / base_price
        
        # Consider market trends
        trend = self.market_analysis.get(commodity, 0)
        if trend > 0.1 and self.ship.patience > 0.7:  # Rising prices, wait if patient
            return False
        
        return profit_margin >= min_profit_margin
    
    def _should_buy_commodity(self, commodity: CommodityType, station: Station, game_time: float) -> int:
        """Decide how much to buy based on personality and market conditions"""
        buy_price = station.market.commodities[commodity]
        base_price = station.market._get_base_price(commodity)
        available_funds = self.ship.credits * self.ship.risk_tolerance
        
        # Don't buy if price is too high
        price_ratio = buy_price / base_price
        if self.ship.personality == AIPersonality.CAUTIOUS and price_ratio > 1.05:
            return 0
        elif self.ship.personality == AIPersonality.AGGRESSIVE and price_ratio > 1.25:
            return 0
        elif price_ratio > 1.15:  # General threshold
            return 0
        
        # Specialists prefer their commodities
        if (self.ship.personality == AIPersonality.SPECIALIST and 
            commodity not in self.ship.preferred_commodities):
            return 0
        
        # Calculate buy amount based on personality
        max_affordable = int(available_funds / buy_price)
        max_space = self.ship.cargo_space_remaining()
        max_stock = station.market.stock_levels[commodity]
        
        if self.ship.personality == AIPersonality.CAUTIOUS:
            buy_amount = min(5, max_affordable, max_space, max_stock)
        elif self.ship.personality == AIPersonality.AGGRESSIVE:
            buy_amount = min(25, max_affordable, max_space, max_stock)
        elif self.ship.personality == AIPersonality.OPPORTUNIST:
            # Buy more if price is really good
            if price_ratio < 0.9:
                buy_amount = min(20, max_affordable, max_space, max_stock)
            else:
                buy_amount = min(10, max_affordable, max_space, max_stock)
        else:  # SPECIALIST
            if commodity in self.ship.preferred_commodities:
                buy_amount = min(30, max_affordable, max_space, max_stock)
            else:
                buy_amount = 0
        
        return max(0, buy_amount)
    
    def _trade_at_station(self, station: Station, game_time: float):
        """Execute trades at current station based on AI personality"""
        trade_interval = 2.0 - self.ship.risk_tolerance  # More aggressive = faster trading
        if game_time - self.ship.last_trade_time < trade_interval:
            return
        
        total_profit = 0
        
        # Sell cargo that meets our criteria
        for commodity, quantity in list(self.ship.cargo_hold.items()):
            if quantity > 0 and self._should_sell_commodity(commodity, station, game_time):
                sell_price = station.market.commodities[commodity]
                base_price = station.market._get_base_price(commodity)
                
                # Sell amount varies by personality
                if self.ship.personality == AIPersonality.CAUTIOUS:
                    sell_amount = min(quantity, 5)
                elif self.ship.personality == AIPersonality.AGGRESSIVE:
                    sell_amount = min(quantity, 15)
                else:
                    sell_amount = min(quantity, 10)
                
                self.ship.cargo_hold[commodity] -= sell_amount
                profit = sell_amount * (sell_price - base_price)
                self.ship.credits += sell_amount * sell_price
                station.market.adjust_price(commodity, sell_amount)
                total_profit += profit
        
        # Buy new cargo based on strategy
        for commodity in CommodityType:
            buy_amount = self._should_buy_commodity(commodity, station, game_time)
            if buy_amount > 0:
                buy_price = station.market.commodities[commodity]
                total_cost = buy_amount * buy_price
                self.ship.cargo_hold[commodity] += buy_amount
                self.ship.credits -= total_cost
                station.market.adjust_price(commodity, -buy_amount)
        
        # Track profit history
        if total_profit != 0:
            self.profit_history.append(total_profit)
            if len(self.profit_history) > 10:
                self.profit_history.pop(0)
        
        self.ship.last_trade_time = game_time
    
    def _plan_movement(self, game_time: float):
        """Plan movement based on personality and market opportunities"""
        # Change destination based on personality
        change_chance = 0.05 + (self.ship.risk_tolerance * 0.15)  # 5-20% chance
        
        if self.ship.destination is None or random.random() < change_chance:
            best_station = None
            best_score = 0
            
            for station in self.galaxy.stations:
                if station.position == self.ship.position:
                    continue
                
                score = self._evaluate_station_opportunity(station, game_time)
                if score > best_score:
                    best_score = score
                    best_station = station
            
            if best_station:
                self.ship.destination = best_station.position
    
    def _evaluate_station_opportunity(self, station: Station, game_time: float) -> float:
        """Evaluate how attractive a station is for trading"""
        score = 0
        distance = self.ship.position.distance_to(station.position)
        
        # Evaluate selling opportunities
        for commodity, quantity in self.ship.cargo_hold.items():
            if quantity > 0:
                sell_price = station.market.commodities[commodity]
                base_price = station.market._get_base_price(commodity)
                profit_potential = quantity * (sell_price - base_price)
                score += profit_potential
        
        # Evaluate buying opportunities
        for commodity in CommodityType:
            buy_price = station.market.commodities[commodity]
            base_price = station.market._get_base_price(commodity)
            
            # Look for potential profit from selling elsewhere
            best_sell_price = 0
            for other_station in self.galaxy.stations:
                if other_station != station:
                    other_price = other_station.market.commodities[commodity]
                    best_sell_price = max(best_sell_price, other_price)
            
            if best_sell_price > buy_price * 1.1:  # 10% profit potential
                potential_profit = (best_sell_price - buy_price) * 10  # Assume buying 10 units
                score += potential_profit
        
        # Adjust for distance and personality
        distance_penalty = distance * (1.0 - self.ship.patience)
        score -= distance_penalty
        
        # Specialists prefer certain station types
        if self.ship.personality == AIPersonality.SPECIALIST:
            if (station.station_type == StationType.MINING_COLONY and 
                CommodityType.MINERALS in self.ship.preferred_commodities):
                score *= 1.5
            elif (station.station_type == StationType.RESEARCH_STATION and 
                  CommodityType.MEDICINE in self.ship.preferred_commodities):
                score *= 1.5
        
        return score
    
    def _move_ship(self):
        """Move ship towards destination with some variation"""
        if self.ship.destination is None:
            return
        
        current = self.ship.position
        dest = self.ship.destination
        
        # Opportunists might take detours
        if (self.ship.personality == AIPersonality.OPPORTUNIST and 
            random.random() < 0.1):  # 10% chance to detour
            # Look for nearby stations with good opportunities
            for station in self.galaxy.stations:
                if (station.position.distance_to(current) <= 2 and
                    station.position != current):
                    opportunity_score = self._evaluate_station_opportunity(station, 0)
                    if opportunity_score > 100:  # Significant opportunity
                        dest = station.position
                        break
        
        # Move one step towards destination
        if current.quadrant_x != dest.quadrant_x:
            if current.quadrant_x < dest.quadrant_x:
                self.ship.position.quadrant_x += 1
            else:
                self.ship.position.quadrant_x -= 1
        elif current.quadrant_y != dest.quadrant_y:
            if current.quadrant_y < dest.quadrant_y:
                self.ship.position.quadrant_y += 1
            else:
                self.ship.position.quadrant_y -= 1
        elif current.sector_x != dest.sector_x:
            if current.sector_x < dest.sector_x:
                self.ship.position.sector_x += 1
            else:
                self.ship.position.sector_x -= 1
        elif current.sector_y != dest.sector_y:
            if current.sector_y < dest.sector_y:
                self.ship.position.sector_y += 1
            else:
                self.ship.position.sector_y -= 1
        else:
            # Reached destination
            self.ship.destination = None

class Galaxy:
    def __init__(self):
        self.size = 8  # 8x8 quadrants like EGA Trek
        self.quadrants: Dict[Tuple[int, int], Dict] = {}
        self.stations: List[Station] = []
        self.ai_ships: List[Ship] = []
        self.ai_traders: List[AITrader] = []
        self.generate_galaxy()
        self.spawn_ai_traders()
    
    def generate_galaxy(self):
        """Generate the galaxy with stations and markets"""
        station_count = 0
        
        for qx in range(self.size):
            for qy in range(self.size):
                quadrant_data = {
                    'stations': [],
                    'planets': [],
                    'asteroids': [],
                    'pirates': []
                }
                
                # 40% chance of having a station in each quadrant
                if random.random() < 0.4:
                    station = self._generate_station(qx, qy, station_count)
                    quadrant_data['stations'].append(station)
                    self.stations.append(station)
                    station_count += 1
                
                # Add some planets (future mining opportunities)
                planet_count = random.randint(0, 2)
                for _ in range(planet_count):
                    planet_pos = Position(qx, qy, random.randint(0, 7), random.randint(0, 7))
                    quadrant_data['planets'].append(planet_pos)
                
                self.quadrants[(qx, qy)] = quadrant_data
    
    def spawn_ai_traders(self):
        """Create AI trader ships with diverse personalities"""
        num_traders = len(self.stations) // 2  # One trader per 2 stations roughly
        
        for i in range(num_traders):
            # Random starting position
            qx = random.randint(0, 7)
            qy = random.randint(0, 7)
            sx = random.randint(0, 7)
            sy = random.randint(0, 7)
            
            # Assign personality
            personality = random.choice(list(AIPersonality))
            
            # Generate personality-based traits
            if personality == AIPersonality.CAUTIOUS:
                risk_tolerance = random.uniform(0.2, 0.4)
                patience = random.uniform(0.6, 0.9)
                credits = random.uniform(3000, 6000)
                cargo_size = random.randint(60, 80)
                name_prefix = "Careful"
            elif personality == AIPersonality.AGGRESSIVE:
                risk_tolerance = random.uniform(0.7, 0.9)
                patience = random.uniform(0.1, 0.4)
                credits = random.uniform(1500, 4000)
                cargo_size = random.randint(80, 120)
                name_prefix = "Bold"
            elif personality == AIPersonality.OPPORTUNIST:
                risk_tolerance = random.uniform(0.5, 0.7)
                patience = random.uniform(0.3, 0.6)
                credits = random.uniform(2500, 7000)
                cargo_size = random.randint(70, 100)
                name_prefix = "Swift"
            else:  # SPECIALIST
                risk_tolerance = random.uniform(0.4, 0.6)
                patience = random.uniform(0.5, 0.8)
                credits = random.uniform(2000, 5000)
                cargo_size = random.randint(50, 90)
                name_prefix = "Expert"
            
            # Assign preferred commodities for specialists
            preferred_commodities = []
            if personality == AIPersonality.SPECIALIST:
                # Pick 1-2 commodities to specialize in
                num_specialties = random.randint(1, 2)
                preferred_commodities = random.sample(list(CommodityType), num_specialties)
            
            ship = Ship(
                name=f"{name_prefix} Trader {i+1}",
                ship_type=ShipType.TRADER,
                position=Position(qx, qy, sx, sy),
                energy=800,
                max_energy=800,
                cargo_hold={commodity: random.randint(0, 3) for commodity in CommodityType},
                max_cargo=cargo_size,
                credits=credits,
                warp_factor=random.uniform(2.0, 4.0),
                max_warp=5.0,
                engines=random.randint(80, 100),
                life_support=100,
                cargo_bay=100,
                trading_computer=random.randint(70, 100),
                shields=random.randint(60, 90),
                personality=personality,
                preferred_commodities=preferred_commodities,
                risk_tolerance=risk_tolerance,
                patience=patience
            )
            
            self.ai_ships.append(ship)
            self.ai_traders.append(AITrader(ship, self))
    
    def _generate_station(self, qx: int, qy: int, station_id: int) -> Station:
        """Generate a random station"""
        station_types = list(StationType)
        station_type = random.choice(station_types)
        
        # Random sector position within quadrant
        sector_x = random.randint(0, 7)
        sector_y = random.randint(0, 7)
        position = Position(qx, qy, sector_x, sector_y)
        
        # Generate market based on station type
        market = self._generate_market(station_type)
        
        station_names = [
            "Alpha Station", "Beta Outpost", "Gamma Trading Post", "Delta Colony",
            "Epsilon Research", "Zeta Mining", "Eta Manufacturing", "Theta Hub"
        ]
        
        name = f"{random.choice(station_names)} {station_id + 1}"
        
        return Station(name, station_type, position, market)
    
    def _generate_market(self, station_type: StationType) -> Market:
        """Generate market prices and stock based on station type"""
        base_prices = {
            CommodityType.FOOD: 100,
            CommodityType.MINERALS: 150,
            CommodityType.TECHNOLOGY: 500,
            CommodityType.MEDICINE: 300,
            CommodityType.LUXURIES: 800,
            CommodityType.FUEL: 80
        }
        
        # Station type affects what they produce/need
        supply_demand = {}
        stock_levels = {}
        
        if station_type == StationType.MINING_COLONY:
            supply_demand = {
                CommodityType.MINERALS: 0.7,  # Cheap minerals (they produce)
                CommodityType.FOOD: 1.5,      # Expensive food (they need)
                CommodityType.TECHNOLOGY: 1.3,
                CommodityType.MEDICINE: 1.2,
                CommodityType.LUXURIES: 1.1,
                CommodityType.FUEL: 0.9
            }
            stock_levels = {
                CommodityType.MINERALS: random.randint(50, 200),
                CommodityType.FOOD: random.randint(5, 20),
                CommodityType.TECHNOLOGY: random.randint(10, 30),
                CommodityType.MEDICINE: random.randint(10, 25),
                CommodityType.LUXURIES: random.randint(5, 15),
                CommodityType.FUEL: random.randint(30, 80)
            }
        elif station_type == StationType.MANUFACTURING_HUB:
            supply_demand = {
                CommodityType.TECHNOLOGY: 0.8,  # Cheap tech (they produce)
                CommodityType.MINERALS: 1.4,    # Expensive minerals (they need)
                CommodityType.FOOD: 1.1,
                CommodityType.MEDICINE: 1.0,
                CommodityType.LUXURIES: 0.9,
                CommodityType.FUEL: 1.1
            }
            stock_levels = {
                CommodityType.TECHNOLOGY: random.randint(40, 120),
                CommodityType.MINERALS: random.randint(10, 30),
                CommodityType.FOOD: random.randint(20, 60),
                CommodityType.MEDICINE: random.randint(15, 40),
                CommodityType.LUXURIES: random.randint(20, 80),
                CommodityType.FUEL: random.randint(20, 50)
            }
        elif station_type == StationType.RESEARCH_STATION:
            supply_demand = {
                CommodityType.MEDICINE: 0.8,    # Cheap medicine (they produce)
                CommodityType.TECHNOLOGY: 0.9,
                CommodityType.FOOD: 1.3,
                CommodityType.MINERALS: 1.2,
                CommodityType.LUXURIES: 1.4,
                CommodityType.FUEL: 1.2
            }
            stock_levels = {
                CommodityType.MEDICINE: random.randint(40, 100),
                CommodityType.TECHNOLOGY: random.randint(20, 60),
                CommodityType.FOOD: random.randint(10, 30),
                CommodityType.MINERALS: random.randint(5, 20),
                CommodityType.LUXURIES: random.randint(5, 15),
                CommodityType.FUEL: random.randint(15, 40)
            }
        else:  # TRADING_POST
            supply_demand = {commodity: random.uniform(0.9, 1.1) for commodity in CommodityType}
            stock_levels = {commodity: random.randint(20, 80) for commodity in CommodityType}
        
        # Calculate current prices
        current_prices = {}
        for commodity in CommodityType:
            base = base_prices[commodity]
            multiplier = supply_demand.get(commodity, 1.0)
            variance = random.uniform(0.9, 1.1)  # ±10% random variance
            current_prices[commodity] = base * multiplier * variance
        
        return Market(current_prices, supply_demand, stock_levels)
    
    def update_ai_traders(self, game_time: float):
        """Update all AI traders"""
        for trader in self.ai_traders:
            trader.update(game_time)
    
    def get_quadrant_info(self, qx: int, qy: int) -> Dict:
        """Get information about a specific quadrant"""
        return self.quadrants.get((qx, qy), {})
    
    def get_ships_in_quadrant(self, qx: int, qy: int) -> List[Ship]:
        """Get all ships in a specific quadrant"""
        ships = []
        for ship in self.ai_ships:
            if ship.position.quadrant_x == qx and ship.position.quadrant_y == qy:
                ships.append(ship)
        return ships

class Game:
    def __init__(self):
        self.galaxy = Galaxy()
        self.player_ship = self._create_player_ship()
        self.game_time = 0.0  # Stardate
        self.turn_count = 0
        self.running = True
        
    def _create_player_ship(self) -> Ship:
        """Create the player's starting ship"""
        # Start near a station if possible
        if self.galaxy.stations:
            start_station = random.choice(self.galaxy.stations)
            position = Position(
                start_station.position.quadrant_x,
                start_station.position.quadrant_y,
                random.randint(0, 7),
                random.randint(0, 7)
            )
        else:
            position = Position(random.randint(0, 7), random.randint(0, 7), 
                              random.randint(0, 7), random.randint(0, 7))
        
        return Ship(
            name="Merchant Vessel",
            ship_type=ShipType.PLAYER,
            position=position,
            energy=1000,
            max_energy=1000,
            cargo_hold={commodity: 0 for commodity in CommodityType},
            max_cargo=100,
            credits=5000.0,
            warp_factor=1.0,
            max_warp=6.0,
            engines=100,
            life_support=100,
            cargo_bay=100,
            trading_computer=100,
            shields=100
        )
    
    def game_loop(self):
        """Main game loop"""
        print("Welcome to EGA Trader!")
        print("A space trading game inspired by EGA Trek")
        print("Type 'help' for commands\n")
        
        while self.running:
            try:
                self.display_status()
                self.display_local_info()
                
                try:
                    command = input("\nCommand: ").strip().lower()
                except EOFError:
                    print("\nNo input available. Exiting game.")
                    break
                    
                self.process_command(command)
                
                # Update game state
                self.game_time += 0.1
                self.turn_count += 1
                
                # Update AI traders every few turns
                if self.turn_count % 3 == 0:
                    self.galaxy.update_ai_traders(self.game_time)
                
            except KeyboardInterrupt:
                print("\nGame interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def process_command(self, command: str):
        """Process player commands"""
        if command.startswith('m') or command == 'move':
            self.handle_move_command(command)
        elif command == 'help' or command == 'h':
            self.show_help()
        elif command == 'scan' or command == 's':
            self.scan_area()
        elif command == 'market' or command == 'mk':
            self.show_market()
        elif command == 'trade' or command == 't':
            self.trade_menu()
        elif command == 'dock' or command == 'd':
            self.dock_at_station()
        elif command == 'quit' or command == 'q':
            self.running = False
        elif command == 'save':
            self.save_game()
        elif command == 'status':
            pass  # Already displayed
        else:
            print("Unknown command. Type 'help' for available commands.")
    
    def handle_move_command(self, command: str):
        """Handle movement commands"""
        if len(command) > 1 and command[0] == 'm':
            # Extract coordinates from command like 'm1234' or 'm12'
            coords = command[1:]
            if len(coords) == 4:  # Quadrant movement
                try:
                    qx, qy, sx, sy = [int(d) for d in coords]
                    if all(0 <= coord <= 7 for coord in [qx, qy, sx, sy]):
                        self.move_to_position(qx, qy, sx, sy)
                    else:
                        print("Coordinates must be between 0-7")
                except ValueError:
                    print("Invalid coordinates format")
            elif len(coords) == 2:  # Sector movement within quadrant
                try:
                    sx, sy = [int(d) for d in coords]
                    if 0 <= sx <= 7 and 0 <= sy <= 7:
                        self.move_to_sector(sx, sy)
                    else:
                        print("Sector coordinates must be between 0-7")
                except ValueError:
                    print("Invalid sector coordinates")
            else:
                print("Movement format: m1234 for quadrant 1,2 sector 3,4 or m34 for sector 3,4")
        else:
            print("Movement format: m1234 for quadrant movement, m34 for sector movement")
    
    def move_to_position(self, qx: int, qy: int, sx: int, sy: int):
        """Move to specific quadrant and sector"""
        old_pos = self.player_ship.position
        energy_cost = abs(qx - old_pos.quadrant_x) + abs(qy - old_pos.quadrant_y)
        energy_cost = energy_cost * 100 + abs(sx - old_pos.sector_x) + abs(sy - old_pos.sector_y)
        
        if self.player_ship.energy >= energy_cost:
            self.player_ship.position = Position(qx, qy, sx, sy)
            self.player_ship.energy -= energy_cost
            print(f"Moved to {self.player_ship.position}. Energy consumed: {energy_cost}")
        else:
            print(f"Insufficient energy. Need {energy_cost}, have {self.player_ship.energy}")
    
    def move_to_sector(self, sx: int, sy: int):
        """Move to sector within current quadrant"""
        old_pos = self.player_ship.position
        energy_cost = abs(sx - old_pos.sector_x) + abs(sy - old_pos.sector_y)
        
        if self.player_ship.energy >= energy_cost:
            self.player_ship.position.sector_x = sx
            self.player_ship.position.sector_y = sy
            self.player_ship.energy -= energy_cost
            print(f"Moved to sector {sx},{sy}. Energy consumed: {energy_cost}")
        else:
            print(f"Insufficient energy. Need {energy_cost}, have {self.player_ship.energy}")
    
    def scan_area(self):
        """Scan current quadrant for stations and other ships"""
        qx, qy = self.player_ship.position.quadrant_x, self.player_ship.position.quadrant_y
        quadrant_info = self.galaxy.get_quadrant_info(qx, qy)
        
        print(f"\nScan results for Quadrant {qx},{qy}:")
        
        if quadrant_info.get('stations'):
            print("Stations:")
            for station in quadrant_info['stations']:
                dist = self.player_ship.position.distance_to(station.position)
                print(f"  {station.name} ({station.station_type.value}) at S{station.position.sector_x},{station.position.sector_y} - Distance: {dist}")
        
        # Show AI ships in quadrant
        ai_ships = self.galaxy.get_ships_in_quadrant(qx, qy)
        if ai_ships:
            print("Other ships:")
            for ship in ai_ships:
                dist = self.player_ship.position.distance_to(ship.position)
                personality_info = f" ({ship.personality.value})" if ship.personality else ""
                cargo_info = f" - Cargo: {ship.total_cargo()}/{ship.max_cargo}"
                print(f"  {ship.name}{personality_info} at S{ship.position.sector_x},{ship.position.sector_y} - Distance: {dist}{cargo_info}")
        
        if quadrant_info.get('planets'):
            print(f"Planets: {len(quadrant_info['planets'])}")
    
    def show_market(self):
        """Show market prices at current location"""
        station = self._get_current_station()
        if not station:
            print("No station at current location. Use 'scan' to find nearby stations.")
            return
        
        print(f"\nMarket prices at {station.name}:")
        print(f"{'Commodity':<12} {'Price':<8} {'Stock':<8}")
        print("-" * 30)
        
        for commodity in CommodityType:
            price = station.market.commodities[commodity]
            stock = station.market.stock_levels[commodity]
            print(f"{commodity.value:<12} ${price:>6.2f} {stock:>6}")
    
    def trade_menu(self):
        """Interactive trading menu"""
        station = self._get_current_station()
        if not station:
            print("No station at current location. Move to a station to trade.")
            return
        
        while True:
            print(f"\nTrading at {station.name}")
            print("1. Buy goods")
            print("2. Sell goods") 
            print("3. View market")
            print("4. Exit trading")
            
            try:
                choice = input("Choice: ").strip()
            except EOFError:
                break
            
            if choice == '1':
                self.buy_goods(station)
            elif choice == '2':
                self.sell_goods(station)
            elif choice == '3':
                self.show_market()
            elif choice == '4':
                break
            else:
                print("Invalid choice")
    
    def buy_goods(self, station: Station):
        """Buy goods from station"""
        print("\nAvailable goods:")
        commodities = list(CommodityType)
        for i, commodity in enumerate(commodities):
            price = station.market.commodities[commodity]
            stock = station.market.stock_levels[commodity]
            print(f"{i+1}. {commodity.value} - ${price:.2f} (Stock: {stock})")
        
        try:
            try:
                choice = int(input("Select commodity (number): ")) - 1
            except EOFError:
                return
            if 0 <= choice < len(commodities):
                commodity = commodities[choice]
                max_affordable = int(self.player_ship.credits / station.market.commodities[commodity])
                max_space = self.player_ship.cargo_space_remaining()
                max_stock = station.market.stock_levels[commodity]
                max_buy = min(max_affordable, max_space, max_stock)
                
                if max_buy <= 0:
                    print("Cannot buy any of this commodity (insufficient credits, space, or stock)")
                    return
                
                try:
                    quantity = int(input(f"Quantity to buy (max {max_buy}): "))
                except EOFError:
                    return
                if 0 < quantity <= max_buy:
                    total_cost = quantity * station.market.commodities[commodity]
                    self.player_ship.cargo_hold[commodity] += quantity
                    self.player_ship.credits -= total_cost
                    station.market.adjust_price(commodity, -quantity)
                    print(f"Bought {quantity} {commodity.value} for ${total_cost:.2f}")
                else:
                    print("Invalid quantity")
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    def sell_goods(self, station: Station):
        """Sell goods to station"""
        available = [(commodity, quantity) for commodity, quantity in self.player_ship.cargo_hold.items() if quantity > 0]
        
        if not available:
            print("No goods to sell")
            return
        
        print("\nYour cargo:")
        for i, (commodity, quantity) in enumerate(available):
            price = station.market.commodities[commodity]
            print(f"{i+1}. {commodity.value} - {quantity} units @ ${price:.2f} each")
        
        try:
            try:
                choice = int(input("Select commodity to sell (number): ")) - 1
            except EOFError:
                return
            if 0 <= choice < len(available):
                commodity, max_quantity = available[choice]
                try:
                    quantity = int(input(f"Quantity to sell (max {max_quantity}): "))
                except EOFError:
                    return
                
                if 0 < quantity <= max_quantity:
                    total_value = quantity * station.market.commodities[commodity]
                    self.player_ship.cargo_hold[commodity] -= quantity
                    self.player_ship.credits += total_value
                    station.market.adjust_price(commodity, quantity)
                    print(f"Sold {quantity} {commodity.value} for ${total_value:.2f}")
                else:
                    print("Invalid quantity")
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    def dock_at_station(self):
        """Dock at nearby station"""
        station = self._get_current_station()
        if station:
            print(f"Already docked at {station.name}")
        else:
            # Look for stations in adjacent sectors
            nearby_stations = []
            for station in self.galaxy.stations:
                if (station.position.quadrant_x == self.player_ship.position.quadrant_x and
                    station.position.quadrant_y == self.player_ship.position.quadrant_y):
                    dist = abs(station.position.sector_x - self.player_ship.position.sector_x) + \
                           abs(station.position.sector_y - self.player_ship.position.sector_y)
                    if dist <= 1:
                        nearby_stations.append((station, dist))
            
            if nearby_stations:
                # Move to closest station
                station, dist = min(nearby_stations, key=lambda x: x[1])
                self.player_ship.position.sector_x = station.position.sector_x
                self.player_ship.position.sector_y = station.position.sector_y
                print(f"Docked at {station.name}")
            else:
                print("No stations within docking range. Use 'scan' to locate stations.")
    
    def _get_current_station(self) -> Optional[Station]:
        """Check if player is at a station"""
        for station in self.galaxy.stations:
            if (station.position.quadrant_x == self.player_ship.position.quadrant_x and
                station.position.quadrant_y == self.player_ship.position.quadrant_y and
                station.position.sector_x == self.player_ship.position.sector_x and
                station.position.sector_y == self.player_ship.position.sector_y):
                return station
        return None
    
    def display_status(self):
        """Display current ship and game status"""
        ship = self.player_ship
        print(f"\n{'='*60}")
        print(f"SHIP STATUS - {ship.name} | Stardate: {self.game_time:.1f}")
        print(f"{'='*60}")
        print(f"Position: {ship.position}")
        print(f"Credits: ${ship.credits:,.2f} | Energy: {ship.energy}/{ship.max_energy}")
        print(f"Cargo: {ship.total_cargo()}/{ship.max_cargo}")
        
        if ship.total_cargo() > 0:
            cargo_str = ", ".join([f"{commodity.value}: {quantity}" 
                                 for commodity, quantity in ship.cargo_hold.items() if quantity > 0])
            print(f"  {cargo_str}")
    
    def display_local_info(self):
        """Display information about current location"""
        station = self._get_current_station()
        if station:
            print(f"Docked at: {station.name} ({station.station_type.value})")
        
        # Show other ships in quadrant
        qx, qy = self.player_ship.position.quadrant_x, self.player_ship.position.quadrant_y
        ai_ships = self.galaxy.get_ships_in_quadrant(qx, qy)
        if ai_ships:
            personalities = {}
            for ship in ai_ships:
                if ship.personality:
                    personalities[ship.personality.value] = personalities.get(ship.personality.value, 0) + 1
            
            if personalities:
                personality_str = ", ".join([f"{count} {ptype}" for ptype, count in personalities.items()])
                print(f"Ships in quadrant: {len(ai_ships)} AI traders ({personality_str})")
            else:
                print(f"Ships in quadrant: {len(ai_ships)} AI traders")
    
    def show_help(self):
        """Display help information"""
        print("\nEGA Trader Commands:")
        print("  move, m1234  - Move to quadrant 1,2 sector 3,4")
        print("  m34          - Move to sector 3,4 in current quadrant")
        print("  scan, s      - Scan current quadrant for stations and ships")
        print("  dock, d      - Dock at nearby station")
        print("  market, mk   - View market prices at current station")
        print("  trade, t     - Enter trading menu")
        print("  status       - Show ship status")
        print("  save         - Save game")
        print("  help, h      - Show this help")
        print("  quit, q      - Exit game")
    
    def save_game(self, filename: str = "trader.sav"):
        """Save the current game state"""
        game_state = {
            'player_ship': asdict(self.player_ship),
            'game_time': self.game_time,
            'turn_count': self.turn_count,
            'galaxy_seed': 42  # For reproducing the same galaxy
        }
        
        with open(filename, 'w') as f:
            json.dump(game_state, f, indent=2)
        print(f"Game saved to {filename}")

if __name__ == "__main__":
    game = Game()
    game.game_loop()