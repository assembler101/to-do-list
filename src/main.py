import kivy
kivy.require('1.11.1')

from kivy.app import App
from kivy.uix.label import Label

from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button

from kivy.graphics.instructions import Canvas
from kivy.graphics import Rectangle
from kivy.graphics import Color
from kivy.graphics import Line
from kivy.properties import ObjectProperty

import sqlite3
from datetime import datetime
from datetime import timedelta

# debugging
from kivy.core.window import Window
import pdb

DATABASE_NAME = 'tasks.db'
TABLE_NAME = 'tasks'

class BtnBehaviorLabel(ButtonBehavior, Label):
    pass

class AppLabel(Label):
    pass

class TaskDisplay(ButtonBehavior, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # colour will change depending on how much time there is left
        with self.canvas:
            self.colour = Color(rgb=(1, 1, 1))
            self.rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(
            size=self._update_size,
            pos=self._update_size
        )

    def _update_size(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class ManageTasks(ScreenManager):
    tasksDisplay = ObjectProperty(None)
    createTask = ObjectProperty(None)
    tasksList = ObjectProperty(None)
    datetimeDueLabel = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.timeLeft = None
        self.STATUS_RGB_COLOURS = {
            'red': (230/255, 34/255, 21/255),
            'yellow': (219/255, 216/255, 37/255),
            'green': (39/255, 214/255, 41/255)
        }
        
        self.displayTasks()

    # Display task functionality
    def displayTasks(self) -> None:
        # clear the previously displayed tasks if they exist to prevent duplicates
        self.tasksList.clear_widgets()

        # load each of the users tasks
        tasks = self.fetchTasks()

        # set the window height according to the number of tasks
        self.tasksList.height = len(tasks)*100

        for task in tasks:
            taskId = task[0]
            title = task[1]
            body = task[2]

            # retrieve the due date if it exists (not NULL)
            if task[3] != None:
                dueDatetime = datetime.fromisoformat(task[3])
                
                self.displayTask(taskId, title, body, dueDatetime)
            else:
                self.displayTask(taskId, title, body)

    def displayTask(self, taskId: int, title: str, body: str, dueDatetime: datetime=None) -> None:
        taskDisplay = TaskDisplay()
        taskDisplay.on_release = lambda: self.editTask(taskId)

        dispTaskAndDelOpt = BoxLayout(orientation='horizontal')

        titleLabel = AppLabel(
            text=title,
            text_size=(Window.size[0], None),
            padding=(Window.size[0]/10, 20)
        )

        dispTaskAndDelOpt.add_widget(titleLabel)

        deleteTaskIcon = BtnBehaviorLabel(
            text='×',
            font_size=36,
            size_hint_x=.2,
            color=(1, 0, 0, 1)
        )
        deleteTaskIcon.on_release = lambda: self.deleteTask(taskId)

        dispTaskAndDelOpt.add_widget(deleteTaskIcon)
        taskDisplay.add_widget(dispTaskAndDelOpt)

        # set the due date if there is an assigned due date
        dueDateLabel = AppLabel()
        if dueDatetime != None:
            # the design of the displayed task depends on how much time there is left
            # work with seconds because timedelta cannot handle hours, mins, etc
            secondsLeft = (dueDatetime - datetime.now()).total_seconds()
            statusColour = None

            DAY = 86400
            HOUR = 3600
            MINUTE = 60

            if secondsLeft >= DAY:
                dueDateLabel.text = '%i day(s) left' % (secondsLeft // DAY)
            elif secondsLeft >= HOUR:
                dueDateLabel.text = '%i hour(s) left' % (secondsLeft // HOUR) 
            elif secondsLeft >= MINUTE:
                dueDateLabel.text = '%i minute(s) left' % (secondsLeft // MINUTE)
            elif secondsLeft <= 0:
                dueDateLabel.text = 'Due date has passed!'

            # set the colour according to time left
            if secondsLeft >= DAY*7:
                statusColour = self.STATUS_RGB_COLOURS['green']
            elif secondsLeft >= HOUR:
                statusColour = self.STATUS_RGB_COLOURS['yellow']
            else:
                statusColour = self.STATUS_RGB_COLOURS['red']

            taskDisplay.colour.rgb = statusColour

        taskDisplay.add_widget(dueDateLabel)
        self.tasksList.add_widget(taskDisplay)

    def fetchTasks(self) -> tuple:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        query = f'''
            SELECT id, title, body, datetime_due FROM {TABLE_NAME}
        '''
        getTasks = cursor.execute(query)
        tasks = getTasks.fetchall()

        conn.close()

        return tasks

    # Create task functionality
    # Manage due date
    def dispDueDate(self):
        if self.timeLeft == None:
            self.datetimeDueLabel.text = '00:00:00'
        else:
            daysLeft = self.timeLeft['days']
            hoursLeft = self.timeLeft['hours']
            minutesLeft = self.timeLeft['minutes']

            self.datetimeDueLabel.text = '%02i:%02i:%02i' % (daysLeft, hoursLeft, minutesLeft)

    def increaseDueDatetime(self, days: int=None, hours: int=None, minutes: int=None) -> None:
        timeLeft = {
            'days': 0,
            'hours': 0,
            'minutes': 0
        }

        if self.timeLeft != None:
            timeLeft = self.timeLeft

        if days:
            timeLeft['days'] += days
        if hours:
            timeLeft['hours'] += hours
        if minutes:
            timeLeft['minutes'] += minutes

        # convert the time durations to the appropriate times. For example, 60 minutes = +1 hour
        if timeLeft['minutes'] >= 60:
            timeLeft['hours'] += timeLeft['minutes']//60
            timeLeft['minutes'] = timeLeft['minutes'] % 60
        if timeLeft['hours'] >= 24:
            timeLeft['days'] += timeLeft['hours']//24
            timeLeft['hours'] = timeLeft['hours'] % 24

        self.timeLeft = timeLeft
        self.dispDueDate()

    def addTask(self, title: str, body: str) -> None:
        # verify the title length is greater than 0
        if len(title) == 0:
            return

        # remove unnecessary trailing and preceding whitespace
        title = title.strip()
        body = body.strip()
        dueDatetime = None

        # store the data into sql database
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # insert due date if it exists
        if self.timeLeft:
            dueDatetime = datetime.now() + timedelta(
                days=self.timeLeft['days'],
                hours=self.timeLeft['hours'],
                minutes=self.timeLeft['minutes']
            )

            query = f'''
                INSERT INTO {TABLE_NAME}(title, body, datetime_due)
                VALUES(?, ?, ?)
            '''
            cursor.execute(query, (title, body, dueDatetime))
        else:
            query = f'''
                INSERT INTO {TABLE_NAME}(title, body)
                VALUES(?, ?)
            '''
            cursor.execute(query, (title, body))

        # update the tasks display GUI
        taskIdQuery = 'SELECT last_insert_rowid()'
        taskId = (cursor.execute(taskIdQuery)).fetchall()[0][0]

        self.tasksList.height = self.tasksList.height + 100
        self.displayTask(taskId, title, body, dueDatetime)

        conn.commit()
        conn.close()

        # go back to home page
        self.createTask.manager.transition.direction = 'right'
        self.createTask.manager.current = 'manage_tasks'

    # Edit task functionality
    def editTask(self, taskId: int) -> None:
        print('edit')

    # Delete task functionality
    def deleteTask(self, taskId: int) -> None:
        # remove the task from the database
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        query = f'''
            DELETE FROM {TABLE_NAME}
            WHERE id = {taskId}
        '''
        cursor.execute(query)

        conn.commit()
        conn.close()

        # update the task display GUI
        self.displayTasks()

class ToDoApp(App):
    def build(self):
        Window.size = (500, 600)

        # create the database if it doesn't exist
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        query = f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(100) NOT NULL,
                body VARCHAR(1000) NOT NULL,
                datetime_due VARCHAR(100)
            );
        '''
        cursor.execute(query)

        conn.commit()
        conn.close()

        return ManageTasks()

if __name__ == '__main__':
    ToDoApp().run()
