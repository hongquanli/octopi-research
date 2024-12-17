import os
# set QT_API environment variable
os.environ["QT_API"] = "pyqt5"

import qtpy
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel
from qtpy.QtCore import QThread, Signal, Qt, QObject, QMetaObject
import sys
import code
import readline
import rlcompleter
import threading
import traceback
import functools
import inspect

class QtCompleter:
    """Custom completer for Qt objects"""
    def __init__(self, namespace):
        self.namespace = namespace
        
    def complete(self, text, state):
        if state == 0:
            if "." in text:
                self.matches = self.attr_matches(text)
            else:
                # Complete global namespace items
                self.matches = self.global_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None
            
    def global_matches(self, text):
        """Compute matches when text is a simple name."""
        matches = []
        n = len(text)
        for word in self.namespace:
            if word[:n] == text:
                matches.append(word)
        return matches
            
    def attr_matches(self, text):
        """Match attributes of an object."""
        # Split the text on dots
        parts = text.split('.')
        if not parts:
            return []
            
        # Find the object we're looking for completions on
        try:
            obj = self.namespace[parts[0]]
            for part in parts[1:-1]:
                if isinstance(obj, GuiProxy):
                    obj = obj.target
                obj = getattr(obj, part)
                
            if isinstance(obj, GuiProxy):
                obj = obj.target
        except (KeyError, AttributeError):
            return []
            
        # Get the incomplete name we're trying to match
        incomplete = parts[-1]
        
        # Get all possible matches
        matches = []
        
        try:
            # Get standard Python attributes
            matches.extend(name for name in dir(obj)
                         if name.startswith(incomplete))
            
            # If it's a QObject, also get Qt properties
            if isinstance(obj, QObject):
                meta = obj.metaObject()
                for i in range(meta.propertyCount()):
                    prop = meta.property(i)
                    name = prop.name()
                    if name.startswith(incomplete):
                        matches.append(name)
                        
            # Get methods with their signatures
            if incomplete:
                matches.extend(
                    f"{name}()" for name, member in inspect.getmembers(obj, inspect.ismethod)
                    if name.startswith(incomplete)
                )
                
        except Exception as e:
            print(f"Error during completion: {e}")
            return []
            
        # Make the matches into complete dots
        if len(parts) > 1:
            matches = ['.'.join(parts[:-1] + [m]) for m in matches]
            
        return matches

class MainThreadCall(QObject):
    """Helper class to execute functions on the main thread"""
    execute_signal = Signal(object, tuple, dict)

    def __init__(self):
        super().__init__()
        self.moveToThread(QApplication.instance().thread())
        self.execute_signal.connect(self._execute)
        self._result = None
        self._event = threading.Event()

    def _execute(self, func, args, kwargs):
        try:
            self._result = func(*args, **kwargs)
        except Exception as e:
            self._result = e
        finally:
            self._event.set()

    def __call__(self, func, *args, **kwargs):
        if QThread.currentThread() is QApplication.instance().thread():
            return func(*args, **kwargs)
        
        self._event.clear()
        self._result = None
        self.execute_signal.emit(func, args, kwargs)
        self._event.wait()
        
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

class GuiProxy:
    """Proxy class to safely execute GUI operations from other threads"""
    def __init__(self, target_object):
        self.target = target_object
        self.main_thread_call = MainThreadCall()

    def __getattr__(self, name):
        attr = getattr(self.target, name)
        if callable(attr):
            @functools.wraps(attr)
            def wrapper(*args, **kwargs):
                return self.main_thread_call(attr, *args, **kwargs)
            return wrapper
        return attr

    def __dir__(self):
        """Support for auto-completion"""
        return dir(self.target)

class EnhancedInteractiveConsole(code.InteractiveConsole):
    """Enhanced console with better completion support"""
    def __init__(self, locals=None):
        super().__init__(locals)
        # Set up readline with our custom completer
        self.completer = QtCompleter(locals)
        readline.set_completer(self.completer.complete)
        readline.parse_and_bind('tab: complete')
        
        # Use better completion delimiters
        readline.set_completer_delims(' \t\n`~!@#$%^&*()-=+[{]}\\|;:\'",<>?')
        
        # Set up readline history
        import os
        histfile = os.path.expanduser("~/.pyqt_console_history")
        try:
            readline.read_history_file(histfile)
        except FileNotFoundError:
            pass
        import atexit
        atexit.register(readline.write_history_file, histfile)

class ConsoleThread(QThread):
    """Thread for running the interactive console"""
    def __init__(self, locals_dict):
        super().__init__()
        self.locals_dict = locals_dict
        self.wrapped_locals = {
            key: GuiProxy(value) if isinstance(value, QObject) else value
            for key, value in locals_dict.items()
        }
        self.console = EnhancedInteractiveConsole(locals=self.wrapped_locals)

    def run(self):
        while True:
            try:
                self.console.interact(banner="""
Squid Microscope Console
-----------------------
Use 'microscope' to access the microscope
""")
            except SystemExit:
                break
