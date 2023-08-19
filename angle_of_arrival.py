from math import *
import psycopg2 as psql
import logging
from gekko import GEKKO

class NetworkManager:

    @staticmethod
    def open():
        try:
            connection = psql.connect(
                database="ttriddev", user="postgres",
                password="rafimochamad", host="167.172.62.14", port=5432)
            cursor = connection.cursor()
            connection.autocommit = True
            return connection, cursor
        except Exception as e:
            logging.error("FAILED TO CONNECTION USER NODE DB")
            return None, None

    @staticmethod
    def close(connection, cursor):
        try:
            if(connection):
                logging.info("SAFE CLOSING CONNECTION USER NODE DB")
                cursor.close()
                connection.close()
        except Exception as e:
            logging.error("FAILED TO SAFE CONNECTION USER NODE DB")

class AngleOfArrival:

    def __init__(self, rsrp: int, lat: float, lon: float, cid: int) -> None:
        self.a = 4
        self.b = 0.0065
        self.c = 17.1
        self.hb = 30
        self.d0 = 100
        self.f = 1.89e9
        self.C_VAL = 3e8
        self.power = 20
        self.A_VAL = 20 * log10(4 * pi * self.d0 / (self.C_VAL / self.f))
        self.B_VAL = 10 * (self.a - self.b * self.hb + self.c / self.hb)
        self.rsrp = rsrp
        self.lat = lat
        self.lon = lon
        self.cid = cid
        self.tower_location = self._get_tower_detail()
        self.m, self.RV = self._optimizer()

    '''
    query db lookup by cid return coordinate
    '''
    def _get_tower_detail(self) -> list:
        try:
            conn, cur = NetworkManager.open()
            cid_val:int = self.cid
            select_query = "SELECT lat, lon FROM sma_cell_data WHERE cid = {cid_val}".format(cid_val=cid_val)
            cur.execute(select_query)
            result = cur.fetchone()
            return list(result)
        except Exception as e:
            logging.error("Error Connection {e}".format(e=str(e)))
        finally:
            NetworkManager.close(conn, cur)

    '''
    convert coordinate tower to radian
    '''
    def get_tower_rad(self) -> list:
        rad_lat = radians(self.tower_location[0])
        rad_lon = radians(self.tower_location[1])
        print("tower radian {radian}".format(radian=[rad_lat, rad_lon]))
        return [rad_lat, rad_lon]

    '''
    get device coordinate in radians
    '''
    def get_device_rad_location(self) -> list:
        rad_lat = radians(self.lat)
        rad_lon = radians(self.lon)
        print("device radian {radian}".format(radian=[rad_lat, rad_lon]))
        return [rad_lat, rad_lon]

    '''
    get actual distance from device to tower
    index 0 -> lat
    index 1 -> lon
    '''
    def get_actual_distance(self) -> float:
        radian_location = self.get_device_rad_location()
        tower_location = self.get_tower_rad()
        d_act = 6371000 * sqrt(((radian_location[1] - tower_location[1]) * cos((radian_location[0] + tower_location[0]) / 2))**2 + (radian_location[0] - tower_location[0])**2)
        print("actual distance {distance}".format(distance=d_act))
        return d_act

    '''
    set optimizer with gekko
    '''
    def _optimizer(self) -> tuple:
        m = GEKKO()
        rv = m.Var(lb=0, ub=80, integer=True)
        RV = rv
        RV.value = 0
        m.Equation(RV>=0)
        return m, RV

    '''
    calculate log for prediction
    '''
    def calculate_log_pred(self) -> float:
        LP = (self.power - self.RV - self.rsrp - self.A_VAL + self.B_VAL * self.m.log10(self.d0)) / self.B_VAL
        print("LP "+str(LP))
        return LP
    
    '''
    set objective function for GEKKO
    '''
    def _set_obj(self):
        d_pred = 10 ** self.calculate_log_pred()
        z = (d_pred - self.get_actual_distance())**2
        print("z val "+str(z))
        return z
    
    def _start(self):
        z = self._set_obj()
        self.m.Minimize(z)
        self.m.options.IMODE = 3
        self.m.options.SOLVER = 1
        self.m.options.MAX_ITER = 1000
        self.m.solve(disp=False)
        obj_z = self.m.options.OBJFCNVAL
        rv = self.RV[0]
        print("objective function value {value}".format(value=obj_z))
        return rv
    
    '''
    predict distance from tower to device
    '''
    def predict_tower_to_device(self) -> float:
        d_pred = 10 ** ((self.power - self._start() - self.rsrp - self.A_VAL + self.B_VAL * log10(self.d0)) / self.B_VAL)
        return d_pred
    
    '''
    predict the coordinate location from device
    '''
    def predict(self) -> list:
        d_pred = self.predict_tower_to_device()
        d_act = self.get_actual_distance()
        m_lat_pred = (self.lat - self.tower_location[0]) * d_pred / d_act + self.tower_location[0]
        m_lon_pred = (self.lon - self.tower_location[1]) * d_pred / d_act + self.tower_location[1]
        return [m_lat_pred, m_lon_pred]
    
solver = AngleOfArrival(rsrp=-92, lat=-6.30218, lon=106.72379, cid=21711)
print(solver.predict())