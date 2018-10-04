import sys
import time
import os
import traceback
import core4.util
import core4.queue.job
import core4.queue.main
import core4.base
from bson.objectid import ObjectId
import importlib
import core4.error
from datetime import timedelta
import core4.logger.mixin

class CoreWorkerProcess(core4.base.CoreBase,
                        core4.logger.mixin.CoreLoggerMixin):

    def start(self, job_id):
        _id = ObjectId(job_id)
        self.identifier = _id
        self.setup_logging()
        self.queue = core4.queue.main.CoreQueue()
        job = self.queue.load_job(_id)
        self.drop_privilege()
        try:
            job.run(**job.args)
            job.__dict__["attempts_left"] -= 1
            self.queue.set_complete(job)
        except core4.error.CoreJobDeferred:
            self.queue.set_defer(job)
        except:
            job.__dict__["attempts_left"] -= 1
            self.queue.set_failed(job)
        finally:
            self.queue.unlock_job(job._id)
            self.raise_privilege()


    def drop_privilege(self):
        pass

    def raise_privilege(self):
        pass

def start():
    proc = CoreWorkerProcess()
    proc.start(str(sys.stdin.read()).strip())